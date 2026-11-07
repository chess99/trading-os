from operating_model import operating_path
from cash_model import calculate_cash, validate_result
from same_base import check_proya_same_base
from decimal import localcontext
from common import D
import independent_cash

def decimal_inputs(value):
    if isinstance(value, float): return str(value)
    if isinstance(value, dict): return {k: decimal_inputs(v) for k,v in value.items()}
    if isinstance(value, list): return [decimal_inputs(x) for x in value]
    return value

def calculate(inputs):
    cases = {}
    own = {}
    for name, spec in inputs["cases"].items():
        params = spec["parameters"]
        operations = operating_path(params)
        result = calculate_cash(params, spec["meta"], operations, spec["bridge_paid_cash"])
        validate_result(params, result)
        if result["feasible"] is not True: raise ValueError("采用路径存在未融资缺口")
        cases[name] = result
        case = {"financial_parameters": decimal_inputs(params), "opening_operating_cash": params["capital"]["opening_operating_cash"], "operating_rows": decimal_inputs(operations), "metadata": spec["meta"]}
        with localcontext() as context:
            context.prec = 80
            independent = independent_cash.path(case, inputs["event"], "current", D, lambda *args: None)
        if independent.get("value") is None: raise ValueError("独立现金账簿未满足可行性约束")
        a = [result["current_value_per_share"], result["year5_terminal_equity_value_per_share"], *result["distributions_per_share"]]
        b = [float(independent["value"]), float(independent["terminal5"]), *[float(x) for x in independent["D5"]]]
        if max(abs(x-y) for x,y in zip(a,b)) > 2e-12: raise ValueError("生产与独立现金/税/权益账簿差异超出既有转码边界")
        own[name] = independent
    base = cases["company-base.raw.json"]
    lo, hi = [cases["company-holder_terminal_" + side + ".raw.json"] for side in ("low", "high")]
    check_proya_same_base(base, lo); check_proya_same_base(base, hi)
    value = {"low": cases["company-core_low.raw.json"]["current_value_per_share"], "high": cases["company-core_high.raw.json"]["current_value_per_share"], "currency": "CNY"}
    holder = {"base_case_distributions_per_share": base["distributions_per_share"], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": lo["year5_terminal_equity_value_per_share"], "high": hi["year5_terminal_equity_value_per_share"]}}}
    return value, holder, {"production": cases, "independent": own}
