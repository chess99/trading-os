import copy
import baseline
import cash_replay as cash

def holder(values):
    return {"base_case_distributions_per_share": values["D"],
            "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": values["Y5_low"], "high": values["Y5_high"]}}}

from cash_interface import condition_events

def calculate(p):
    events = condition_events(p["event"])["events"]
    event = next(x for x in events if x["h_condition_point"]["name"] == p["adopted_condition_point"])
    cases = {}
    for item in p["cases"]:
        original = baseline.run(item["method"], item["scenario"], n=item["years"], override=item["parameters"])
        name = item["method"] + ":" + item["scenario"]
        cases[name] = cash.run(item["method"], item["scenario"], original, event, n=item["years"], override=item["parameters"])
    values = {"D": cases["product:base"]["distributions"], "Y5_low": cases["product:terminal_low"]["terminal_year5"], "Y5_high": cases["product:terminal_high"]["terminal_year5"]}
    return {"low": cases["product:core_low"]["value_per_share"], "high": cases["product:core_high"]["value_per_share"], "currency": "CNY"}, holder(values), cases
