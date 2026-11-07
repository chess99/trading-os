import copy
import baseline
import cash_replay as cash

def holder(values):
    return {"base_case_distributions_per_share": values["D"],
            "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": values["Y5_low"], "high": values["Y5_high"]}}}

def calculate(p):
    cases = {}
    for item in p["cases"]:
        args = dict(item["parameters"])
        original = baseline.scenario(item["name"], method=item["method"], **args)
        cases[item["name"]] = cash.scenario(item["name"], original, p["event"], method=item["method"], **args)
    values = {"D": cases["A_base"]["distributions"], "Y5_low": cases["holder_low"]["year5_continuation"], "Y5_high": cases["holder_high"]["year5_continuation"]}
    return {"low": cases["A_low"]["value_per_share"], "high": cases["A_high"]["value_per_share"], "currency": "CNY"}, holder(values), cases
