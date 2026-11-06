from model import run_case

def calculate(inputs):
    result = run_case(inputs, "dcf")
    if not result["current_unconditional_eligible"]:
        raise ValueError("采用基准的权益行动不相容")
    terminals = [x["year5"]["per_share"] for x in result["endpoints"]]
    value = round(result["current"]["per_share"], 2)
    holder = {"base_case_distributions_per_share": result["distributions"],
              "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": min(terminals), "high": max(terminals)}}}
    return {"low": value, "high": value, "currency": "CNY"}, holder, result
