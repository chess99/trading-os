"""银河娱乐 2026-H1；python3 2026-H1.py 以同目录输入重建结果。"""
from pathlib import Path
import json
from math import isclose

ROOT = Path(__file__).resolve().parent


def present(values, rate):
    return sum(value / (1 + rate) ** year for year, value in enumerate(values, start=1))


def price(case, shares, opening_cash, annual_upgrade):
    rate = case["rate"]
    assert len(case["ebitda"]) == len(case["growth_spend"]) == 6
    assert len(case["dividends"]) == 5
    flows = [
        earnings - case["maintenance"] - case["operating_drag"] - expansion
        for earnings, expansion in zip(case["ebitda"], case["growth_spend"])
    ]
    dividends = case["dividends"]
    retained = opening_cash
    for cashflow, dividend in zip(flows[:5], dividends):
        retained += cashflow - dividend * shares
        assert retained >= 0
    # 第六个周年末接近批给到期；续期年度现金已经扣除持续履约与维护费用。
    follow = [flows[5] - case["renewal_cost"]]
    if case["renewed_annual_ebitda"]:
        renewed_cash = (case["renewed_annual_ebitda"] - case["maintenance"]
                        - case["operating_drag"] - annual_upgrade)
        follow.extend([renewed_cash] * 10)
    follow[-1] += case["residual"]
    terminal = (retained + present(follow, rate)) / shares
    total = present(dividends, rate) + terminal / (1 + rate) ** 5
    assert isclose(retained + sum(dividends) * shares, opening_cash + sum(flows[:5]))
    return {"price":round(total, 2), "terminal":round(terminal, 2),
            "terminal_pv_fraction":round(terminal / (1 + rate) ** 5 / total, 3),
            "year5_retained_billion":round(retained, 3)}


def calculate(data):
    facts = data["facts"]
    shares = facts["issued_nov"] + max(0, facts["h1_dilutive_awards"] - facts["nov_award_issued"])
    opening = (facts["june_net_liquid"] - facts["issued_oct"] * facts["sept_dividend"]
               - facts["cash_cushion"] - facts["minority"])
    cases = data["cases"]
    result = {name:price(case, shares, opening, data["renew_annual_upgrade"])
              for name, case in cases.items()}
    anchors = {name:row["price"] for name,row in result.items()}
    assert list(anchors.values()) == sorted(anchors.values())
    # 辅助法直接以首年正常化 EBIT 估值，剔除四期尚待交付的投资和收益。
    secondary = []
    for name, multiple in zip(("base_low", "base_high"), data["secondary_ebit_multiple"]):
        ebit = cases[name]["ebitda"][0] - data["normalized_da"]
        secondary.append(round((ebit * multiple + opening) / shares, 2))
    base = cases["base_low"]
    stresses = {
        "no_renewal":dict(base, renewed_annual_ebitda=0, renewal_cost=0),
        "growth_budget_overrun_25pct":dict(base, growth_spend=[x*1.25 for x in base["growth_spend"]]),
        "all_ebitda_down_10pct":dict(base, ebitda=[x*.90 for x in base["ebitda"]],
                                   renewed_annual_ebitda=base["renewed_annual_ebitda"]*.90)
    }
    stress_values = {name:price(case, shares, opening, data["renew_annual_upgrade"])["price"]
                     for name, case in stresses.items()}
    return {"single_factor_base_low":stress_values, "symbol":data["symbol"], "report_period":data["report_period"],
            "value_range":{"low":anchors["base_low"], "high":anchors["base_high"], "currency":"HKD"},
            "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"HKD",
                 "model_as_of":data["as_of"],"base_case_distributions_per_share":cases["base_low"]["dividends"],
                 "base_case_terminal_equity_value_range_per_share":{"year_5":{
                 "low":result["base_low"]["terminal"],"high":result["base_high"]["terminal"]}}},
            "scenarios":anchors,"sensitivity":result,"secondary_range":secondary,
            "opening_common_liquidity_billion":round(opening,3),"diluted_shares_billion":round(shares,9)}


if __name__ == "__main__":
    # 零折现、零资本开支且没有续期：六年利润各2，初始现金3，终局处置2，共17。
    example = dict(rate=0, maintenance=0, operating_drag=0, ebitda=[2]*6, growth_spend=[0]*6,
                   dividends=[1]*5, renewal_cost=0, renewed_annual_ebitda=0, residual=2)
    assert price(example, 1, 3, 0)["price"] == 17
    source = json.loads((ROOT / "2026-H1-input.json").read_text())
    output = calculate(source)
    (ROOT / "2026-H1-output.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")
