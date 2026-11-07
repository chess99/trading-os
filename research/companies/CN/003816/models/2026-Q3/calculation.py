import baseline
import cash_replay as cash

def calculate(p):
    cases = {}
    for name, args in p["cases"].items():
        original = baseline.simulate(args)
        cases[name] = cash.bridge(original, p["event"])
    value_key = "value"
    value = {"low": cases["core_low"][value_key], "high": cases["core_high"][value_key], "currency": "CNY"}
    base = cases["base"]
    d = [row["dps"] for row in base["rows"][:5]]
    low, high = [sum(row["dps"] / (1 + rate) ** (i - 4) for i, row in enumerate(base["rows"]) if i >= 5) for rate in [0.085, 0.075]]
    holder = {"base_case_distributions_per_share": d, "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low, "high": high}}}
    return value, holder, cases
