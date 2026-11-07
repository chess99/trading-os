import model

def calculate(inputs):
    c, policy = inputs["budget"], inputs["policy"]
    names = ("base_maturity", "operating_discount_plus_100bp", "operating_discount_minus_100bp")
    paths = {name: model.run_path(model.variant(c, name), policy, name) for name in names}
    base, lo, hi = [paths[name] for name in names]
    if any(p["holder_model"] is None for p in paths.values()): raise ValueError("采用路径无法构造持有人现金")
    value = {"low": round(lo["method1_per_current_economic_unit"], 2), "high": round(hi["method1_per_current_economic_unit"], 2), "currency": "CNY"}
    holder = {"base_case_distributions_per_share": [round(x, 6) for x in base["holder_model"]["D_per_current_economic_unit"]],
        "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": round(lo["holder_model"]["Y5_per_current_economic_unit"], 2), "high": round(hi["holder_model"]["Y5_per_current_economic_unit"], 2)}}}
    return value, holder, paths
