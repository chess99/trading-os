import copy
import baseline
import cash_replay as cash
from bridge_core import Context

def run_original(code, spec, inputs):
    if code == "300750": return baseline.run(method=spec["method"], **spec["parameters"])
    if code == "688100": return baseline.evaluate_case(inputs["original_inputs"], spec["path"], spec["financial_share_condition"], spec["overrides"])
    if code == "600887": return baseline.forecast(next(x for x in baseline.CASES if x[0] == spec["name"]), years=spec["years"])
    if code == "600690": return baseline.calculate(spec["rate"], spec["shock"], spec["entry"], spec["years"])
    return baseline.run(copy.deepcopy(spec["params"]), spec["years"], copy.deepcopy(spec["continuation_switch"]))

def run_cash(code, spec, inputs, original):
    aux = None
    if code == "688100":
        facts, config, p = baseline.validate_case_inputs(inputs["original_inputs"], spec["path"], spec["financial_share_condition"], spec["overrides"])
        flows = [p["aux_normal_owner_cash"] * (1 + p["aux_growth"]) ** i for i in range(1, 11)]
        ev = sum(v / (1 + p["discount_rate"]) ** i for i, v in enumerate(flows, 1))
        ev += flows[-1] / p["discount_rate"] / (1 + p["discount_rate"]) ** 10
        aux = {"aux_flows": flows, "aux_ev": ev}
    context = Context(code, spec["key"], original, inputs["event"], True, True, True, aux)
    cash.CTX = context
    if code == "300750":
        # The public handcase tests call this same law/sale kernel.
        import importlib.util
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / "2026-Q3-engine.py"
        if path.exists():
            loader = importlib.util.spec_from_file_location("current_catl_kernel", path)
            kernel = importlib.util.module_from_spec(loader); loader.loader.exec_module(kernel)
            cash.law, cash.sale = kernel.law, kernel.sale
        return cash.run(method=spec["method"], **spec["parameters"])
    if code == "688100": return cash.evaluate_case(inputs["original_inputs"], spec["path"], spec["financial_share_condition"], spec["overrides"])
    if code == "600887": return cash.forecast(next(x for x in cash.CASES if x[0] == spec["name"]), years=spec["years"])
    if code == "600690": return cash.calculate(spec["rate"], spec["shock"], spec["entry"], spec["years"])
    return cash.run(copy.deepcopy(spec["params"]), spec["years"], copy.deepcopy(spec["continuation_switch"]))

def calculate(p):
    code = p["code"]
    cases = {s["key"]: run_cash(code, s, p, run_original(code, s, p)) for s in p["cases"]}
    lo, hi, base = [cases["models/volume/" + k] for k in ("core_low", "core_high", "base")]
    value = {"low": lo["PV"], "high": hi["PV"], "currency": "CNY"}
    d, low, high = base["D"][:5], lo["TV5"], hi["TV5"]
    holder = {"base_case_distributions_per_share": d, "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low, "high": high}}}
    return value, holder, cases
