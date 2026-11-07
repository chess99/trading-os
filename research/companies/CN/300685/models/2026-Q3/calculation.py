import copy
import baseline
import cash_replay as cash

def calculate(p):
    spec = copy.deepcopy(baseline.INPUT)
    rows = baseline.simulate(spec)
    original = {"inputs": spec, "rows": rows, "valuation": baseline.value(rows, spec),
        "low": baseline.value(rows, spec, .095, .02, .29, .85, 18), "high": baseline.value(rows, spec, .085, .025, .31, .75, 22)}
    current = cash.selected_cash({"scenarios": {"base": original}}, p["event"], True)[0]
    base = current["base"]
    value = {"low": base["low"]["per_share"], "high": base["high"]["per_share"], "currency": "CNY"}
    d = [r["distribution"] / cash.SHARES for r in base["rows"][:5]]
    low, high = base["low"]["terminal_per_share"], base["high"]["terminal_per_share"]
    value = {**value, "low": round(value["low"], 1), "high": round(value["high"], 1)}
    holder = {"base_case_distributions_per_share": d, "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low, "high": high}}}
    return value, holder, current
