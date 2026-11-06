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
        original = baseline.run(**kw)
        cash.FROZEN_ROWS, cash.FROZEN_RESULT = original["rows"], original
        cases[name] = cash.run(**kw)
    base = cases["base"]
    value = {"low": base["valuation"][0]["value"], "high": base["valuation"][1]["value"], "currency": "CNY"}
    d = [x["dps"] for x in base["rows"][:5]]
    low, high = base["valuation"][0]["terminal"], base["valuation"][1]["terminal"]
    holder = {"base_case_distributions_per_share": d, "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low, "high": high}}}
    return value, holder, cases
