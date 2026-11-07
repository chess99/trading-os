import copy
import baseline
import cash_replay as cash

def calculate(p):
    specs = {"base": {}, "core_low": {"rate": .105, "margin_shift": -.015}, "core_high": {"rate": .095, "margin_shift": .015}}
    old = {"cases": {k: baseline.model(dict(baseline.BASE, **v)) for k, v in specs.items()}, "auxiliary_earnings_power": baseline.crosscheck()}
    current = cash.selected_cash(old, p["event"], True)[0]
    base = current["cases"]["base"]
    lo, hi = current["cases"]["core_low"], current["cases"]["core_high"]
    value = {"low": lo["value"], "high": hi["value"], "currency": "CNY"}
    d = [r["dps"] for r in base["rows"][:5]]
    low, high = [sum(r["dps"] / (1 + rate) ** (r["year"] - 5) for r in base["rows"][5:]) for rate in (.105, .095)]
    value = {**value, "low": round(value["low"], 1), "high": round(value["high"], 1)}
    holder = {"base_case_distributions_per_share": d, "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low, "high": high}}}
    return value, holder, current
