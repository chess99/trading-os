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
        original = baseline.production(**kw)
        cash.FROZEN_ROWS, cash.FROZEN_RESULT = original["years"], original
        cases[name] = cash.production(**kw)
    from same_base_holder import source_order
    base = cases["base"]
    value = {"low": cases["core_low"]["value_per_share"], "high": cases["core_high"]["value_per_share"], "currency": "CNY"}
    d = [x["ordinary_dividend"] / cash.SHARES for x in base["years"][:5]]
    low, high = source_order(base, .10, cash.SHARES), source_order(base, .09, cash.SHARES)
    holder = {"base_case_distributions_per_share": d, "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low, "high": high}}}
    return value, holder, cases
