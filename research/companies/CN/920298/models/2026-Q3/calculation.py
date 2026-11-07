import model

def calculate(doc):
    discard = lambda *args: None
    operating = model.build_operating(doc, discard, discard)
    chains = {name: model.cash_chain(doc, operating, 0, name, discard, discard) for name in doc["common"]["endpoints"]}
    result = model.valuation(doc, operating, chains)
    endpoints, h = result["endpoints"], result["return_model"]
    value = {"low": float(endpoints["low"]["holder_current_per_share"]), "high": float(endpoints["high"]["holder_current_per_share"]), "currency": "CNY"}
    holder = {"base_case_distributions_per_share": [float(x) for x in h["distributions_per_share"]],
        "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": float(endpoints["low"]["Y5_per_share"]), "high": float(endpoints["high"]["Y5_per_share"])}}}
    return value, holder, result
