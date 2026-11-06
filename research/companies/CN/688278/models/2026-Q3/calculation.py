import copy
import baseline
import cash_replay as cash

def holder(values):
    return {"base_case_distributions_per_share": values["D"],
            "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": values["Y5_low"], "high": values["Y5_high"]}}}

def calculate(p):
    cfg = copy.deepcopy(p["original_inputs"])
    cfg.update(p_release_year=12, b_release_year=15, capital_release=True, retire_idle_assets=True, exit_year=40)
    original = baseline.simulate(cfg)
    result = cash.simulate(cfg, original, p["event"])
    low, high = cash.value(result, .115), cash.value(result, .10)
    values = {"D": low["dps"], "Y5_low": low["tv5"], "Y5_high": high["tv5"]}
    return {"low": low["value"], "high": high["value"], "currency": "CNY"}, holder(values), result
