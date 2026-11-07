from copy import deepcopy
import picc_model as engine
from sotp_five_year_bridge import validate_scope, bridge_case

def calculate(inputs):
    operating, config = inputs["operating"], inputs["bridge"]
    scenario = operating["scenarios"]["central"]
    financing = operating["financing_branches"]["not_completed"]
    states = {}
    def checkpoint(kind, payload):
        if kind == "year_completed" and payload["year"] <= 5:
            states[payload["year"]] = deepcopy(payload)
    a = engine.forecast(operating, scenario, financing, checkpoint=checkpoint)
    b = engine.sotp(operating, scenario, a["initial"])
    saved = {"status": "success", "scenario": "central", "financing": "not_completed", "A": a, "B": b}
    validate_scope(config, operating, saved, states)
    cases = {c["id"]: bridge_case(config, c, operating, saved, states) for c in config["combinations"]}
    corners = [cases[c["id"]] for c in config["combinations"] if c["role"] == "core_corner"]
    values = [c["current_bridge"]["current_per_share"] for c in corners]
    terminals = [c["terminal_bridge"]["holder_terminal_per_share5"] for c in corners]
    holder = {"base_case_distributions_per_share": a["D1_to_D5"],
              "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": round(min(terminals), 2), "high": round(max(terminals), 2)}}}
    return {"low": round(min(values), 2), "high": round(max(values), 2), "currency": "CNY"}, holder, {"operating": saved, "finite_bridges": cases}
