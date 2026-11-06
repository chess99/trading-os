import bank_engine as engine

def calculate(inputs):
    specification = next(s for s in inputs["scenarios"] if s["name"] == "policy_continuity")
    scenario = engine.deep_merge(inputs["scenario_defaults"], specification)
    result = engine.simulate(inputs, scenario)
    if result["violations"] or not all(v["feasible"] for v in result["values"].values()):
        raise ValueError("采用基准的资本或分配路径未通过")
    values = [v["current_per_share"] for v in result["values"].values()]
    terminals = [v["year5_terminal_per_share"] for v in result["values"].values()]
    holder = {"base_case_distributions_per_share": result["five_actual_distribution_buckets_per_share"],
              "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": round(min(terminals), 2), "high": round(max(terminals), 2)}}}
    return {"low": round(min(values), 2), "high": round(max(values), 2), "currency": "CNY"}, holder, result
