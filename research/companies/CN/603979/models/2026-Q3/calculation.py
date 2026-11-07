import baseline
import cash_replay as cash

def calculate(inputs):
    original = baseline.produce()
    shares = original["shares_billion"]
    cases = {name: cash.replay(original["scenarios"][name], shares, True) for name in ("base", "core_low", "core_high")}
    conditional = {name: cash.replay(original["conditional_year5"][name], shares, True, prefix=cases["base"]["years"][:5]) for name in ("core_low", "core_high")}
    value = {"low": cases["core_low"]["pv_per_share"], "high": cases["core_high"]["pv_per_share"], "currency": "CNY"}
    value = {**value, "low": round(value["low"], 2), "high": round(value["high"], 2)}
    holder = {"base_case_distributions_per_share": [r["distribution_per_share"] for r in cases["base"]["years"][:5]],
              "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": conditional["core_low"]["terminal_year5_per_share"], "high": conditional["core_high"]["terminal_year5_per_share"]}}}
    return value, holder, {"cases": cases, "conditional_year5": conditional}
