import copy
import baseline
import cash_replay as cash

def holder(values):
    return {"base_case_distributions_per_share": values["D"],
            "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": values["Y5_low"], "high": values["Y5_high"]}}}

def calculate(p):
    inputs = p["original_inputs"]
    old = {name: baseline.run_case(inputs, name) for name in ("base", "core_low", "core_high")}
    new = {name: cash.run_case(inputs, name, value, p["event"]) for name, value in old.items()}
    base = old["base"]
    terminals = {}
    for side in ("low", "high"):
        cfg = copy.deepcopy(base["config"])
        for key in ("discount", "terminal_growth"): cfg[key] = copy.deepcopy(old["core_" + side]["config"][key])
        rows = baseline.operating_path(inputs, cfg)
        assert rows[:5] == base["operating_rows"][:5]
        terminals["year5_" + side] = (baseline.operating_value_at(rows, cfg, 5)["total"] + base["holder_ledger"]["end_group_free"] + base["opening_bridge"]["other_nonoperating_investments_value"]) / inputs["shares"]
    end = cash.holder_endpoints(terminals, base, new, inputs["shares"])
    values = {"main_low": new["core_low"]["current_value_per_share"], "main_high": new["core_high"]["current_value_per_share"],
              "D": new["base"]["holder_ledger"]["distributions_per_share"], "Y5_low": end["year5_low"], "Y5_high": end["year5_high"]}
    return {"low": values["main_low"], "high": values["main_high"], "currency": "CNY"}, holder(values), {"cases": new, "holder_endpoint": end}
