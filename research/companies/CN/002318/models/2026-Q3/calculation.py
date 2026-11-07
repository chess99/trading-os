import copy
import baseline
import cash_replay as cash

def calculate(p):
    cases = {}
    for name, spec in p["cases"].items():
        for key, value in spec.get("globals", {}).items():
            setattr(baseline, key, copy.deepcopy(value))
            setattr(cash, key, copy.deepcopy(value))
        cash.EVENT_ADVANCE = float(p["event"]["advance_model_units"])
        cash.EVENT_TREASURY_ADDITION = float(p["event"].get("treasury_addition_model_units", "0"))
        kw = copy.deepcopy(spec["arguments"])
        if name == "auxiliary":
            cases[name] = cash.secondary()
            continue
        original = baseline.run(**kw)
        cash.FROZEN_ROWS, cash.FROZEN_RESULT = original["years"], original
        cases[name] = cash.run(**kw)
    base = cases["base"]
    value = {"low": cases["core_low"]["PV"], "high": cases["core_high"]["PV"], "currency": "CNY"}
    d = base["DPS5"]
    low, high = cases["holder_low"]["TV5"], cases["holder_high"]["TV5"]
    holder = {"base_case_distributions_per_share": d, "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low, "high": high}}}
    return value, holder, cases
