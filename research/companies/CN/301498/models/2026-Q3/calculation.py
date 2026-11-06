import copy
import baseline
import cash_replay as cash

def calculate(p):
    base = baseline.roll(baseline.scenarios()["base"])
    for key, rate in [("valuation", None), ("low", .115), ("high", .10)]: base[key] = baseline.value(base, rate)
    current = cash.selected_cash({"scenarios": {"base": base}}, p["event"], True)[0]
    base = current["base"]
    value = {"low": base["low"]["value_per_share"], "high": base["high"]["value_per_share"], "currency": "CNY"}
    d = [r["dps"] for r in base["rows"][:5]]
    low, high = base["low"]["terminal_per_share"], base["high"]["terminal_per_share"]
    value = {**value, "low": round(value["low"], 2), "high": round(value["high"], 2)}
    holder = {"base_case_distributions_per_share": d, "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low, "high": high}}}
    return value, holder, current
