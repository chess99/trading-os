import baseline
import cash_replay as cash

def calculate(inputs):
    cases = {name: cash.replay(baseline.run(spec["parameters"], spec["horizon"])) for name, spec in inputs["cases"].items()}
    value = {"low": cases["core_low"]["value"], "high": cases["core_high"]["value"], "currency": "CNY"}
    d, low, high = cases["base"]["d"], cases["holder_terminal_low"]["tv5"], cases["holder_terminal_high"]["tv5"]
    holder = {"base_case_distributions_per_share": d, "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low, "high": high}}}
    return value, holder, cases
