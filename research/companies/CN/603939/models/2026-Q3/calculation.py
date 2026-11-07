import copy
import baseline
import cash_replay as cash

def holder(values):
    return {"base_case_distributions_per_share": values["D"],
            "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": values["Y5_low"], "high": values["Y5_high"]}}}

def calculate(p):
    cases = {}
    for item in p["cases"]:
        args, years = item["parameters"], item["years"]
        original = baseline.simulate(args, years=years)
        cases[item["name"]] = cash.simulate(args, original, p["event"], years=years)
    values = {"D": cases["base"]["five_dividends_per_share"], "Y5_low": cases["holder_y5_low"]["year5_continuation_per_share"], "Y5_high": cases["holder_y5_high"]["year5_continuation_per_share"]}
    return {"low": cases["core_low"]["value_per_share"], "high": cases["core_high"]["value_per_share"], "currency": "CNY"}, holder(values), cases
