from model import run_all
from y5_bridge import bridge
from igct_bridge import check

def calculate(inputs):
    raw = run_all(inputs["budget"], inputs["details"], inputs["policy"])
    shares = inputs["budget"]["source_facts"]["shares"]
    converted = {}
    paths = [("base/main", raw["paths"]["base"]["main"])] + [("sensitivity/" + x["name"], x["result"]) for x in raw["isolated_sensitivities"]]
    for label, path in paths:
        annual = path["annual"]
        b = bridge([r["fcfe_common"] for r in annual], path["opening"]["finance_common"], annual[4]["financial_closing_common"], path["terminal"]["normal_fcfe_common"], path["parameters"]["terminal_growth"], path["parameters"]["ke"], shares, path["D1_D5"])
        if b["current_resource_equity_bn_reproduced"] != path["free_operating_equity_value_bn"]: raise ValueError("资源桥重复计价或口径不符")
        converted[label] = b
    base_path = raw["paths"]["base"]["main"]
    for item in raw["isolated_sensitivities"]:
        if item["name"] in ("ke_higher", "ke_lower"):
            assert item["result"]["D1_D5"] == base_path["D1_D5"]
            assert [r["parent_sub_bridge"] for r in item["result"]["annual"][:5]] == [r["parent_sub_bridge"] for r in base_path["annual"][:5]]
    lo, hi = [converted["sensitivity/" + name] for name in ("ke_higher", "ke_lower")]
    value = {"low": round(lo["finite_five_year_holder_PV_per_share_diagnostic"], 2), "high": round(hi["finite_five_year_holder_PV_per_share_diagnostic"], 2), "currency": "CNY"}
    holder = {"base_case_distributions_per_share": converted["base/main"]["D1_D5_actual_saved_per_share"], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": lo["same_base_year5_resource_per_share"], "high": hi["same_base_year5_resource_per_share"]}}}
    igct = check(raw, inputs["budget"]["common_budget"])
    return value, holder, {"model": raw, "finite_five_year_bridge": converted, "igct": igct}
