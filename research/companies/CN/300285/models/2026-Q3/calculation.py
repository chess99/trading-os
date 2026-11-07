import copy
import baseline
import cash_replay as cash

def calculate(p):
    spec = copy.deepcopy(baseline.BASE); spec["name"] = "Base"
    original = {"scenarios": {"Base": baseline.budget(spec)}}
    current = cash.selected_cash(original, p["event"], True)[0]
    base = current["base"]
    value = {"low": base["valuation"][0]["pv"], "high": base["valuation"][1]["pv"], "currency": "CNY"}
    d = base["base5D"]
    low, high = base["valuation"][0]["tv5"], base["valuation"][1]["tv5"]
    value = {**value, "low": round(value["low"], 2), "high": round(value["high"], 2)}
    holder = {"base_case_distributions_per_share": d, "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low, "high": high}}}
    return value, holder, current
