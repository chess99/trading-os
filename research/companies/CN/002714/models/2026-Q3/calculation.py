import baseline
import cash_replay as cash

def calculate(inputs):
    context = cash.context()
    condition = cash.condition(inputs["display_condition"], context)
    cases = {}
    for name, rate in inputs["rates"].items():
        original = baseline.simulate(name, years=inputs["horizon"], rate=rate)
        if not original["feasible"]: raise ValueError("采用经营路径无法完整计算")
        operating = [{**{k: row[k] for k in cash.OPERATING_FIELDS}, "physical_ending_state": {k: row["ending_state"][k] for k in ("fixed", "bio", "rou", "working", "investment", "portfolio")}} for row in original["rows"]]
        result = cash.simulate_saved(baseline.initial(), operating, original["rows"], name, rate, context, condition)
        if result["feasible"] is not True: raise ValueError((name, result.get("failure_type"), result["rows"][-1].get("reason"), result["rows"][-1].get("message")))
        cases[name] = result
    base = cases["base"]
    endpoints = [cash.summarize(base["rows"], "base", rate, base["final_state"])["terminal_y5"] for rate in (.11, .10)]
    value = {"low": round(cases["core_low"]["current_value"], 1), "high": round(cases["core_high"]["current_value"], 1), "currency": "CNY"}
    holder = {"base_case_distributions_per_share": [round(x, 6) for x in base["dps5"]], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": round(endpoints[0], 2), "high": round(endpoints[1], 2)}}}
    return value, holder, cases
