import baseline
import cash_replay as cash

def calculate(inputs):
    cases = {}
    for name in cash.CURRENT_CASES:
        original = baseline.run(name, "unit_economics", inputs["horizon"])
        cases[name] = cash.run(name, "unit_economics", inputs["horizon"], frozen_path=original, event_condition=inputs["condition"])
        if cases[name]["status"] != "feasible": raise ValueError((name, cases[name].get("stop")))
    holder = cash.holder_contract({("unit_economics", name): value for name, value in cases.items()}, "")
    # The public wrapper binds the report information version; this function calculates cash.
    holder = {k: holder[k] for k in ("base_case_distributions_per_share", "base_case_terminal_equity_value_range_per_share")}
    value = {"low": cases["core_low"]["value"], "high": cases["core_high"]["value"], "currency": "CNY"}
    return value, holder, cases
