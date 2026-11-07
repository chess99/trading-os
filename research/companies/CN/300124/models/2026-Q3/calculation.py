import copy
import baseline
import cash_replay as cash

def calculate(p):
    original = {"scenarios": {name: baseline.run(baseline.SCENARIOS[name]) for name in ("base", "core_low", "core_high")}, "method2": baseline.method2()}
    current = cash.selected_cash(original, p["event"], True)[0]
    lo, hi, base = [current["cases"][name] for name in ("core_low", "core_high", "base")]
    value = {"low": lo["pv_per_share"], "high": hi["pv_per_share"], "currency": "CNY"}
    d = [r["distribution_per_share"] for r in base["years"][:5]]
    low, high = lo["year5_terminal_per_share"], hi["year5_terminal_per_share"]
    value = {**value, "low": round(value["low"], 2), "high": round(value["high"], 2)}
    holder = {"base_case_distributions_per_share": d, "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low, "high": high}}}
    return value, holder, current
