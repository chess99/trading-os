"""运行 python 2026-Q3.py，输出港元普通股价值、分配与权益桥。"""
import importlib.util
import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
here = Path(__file__).resolve().parent
data = json.loads((here / "2026-Q3-input.json").read_text(encoding="utf-8"))
source = next(p / data["issuer_directory"] for p in here.parents if (p / data["issuer_directory"]).is_dir())
spec = importlib.util.spec_from_file_location("cnooc_issuer", source / "model.py")
issuer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(issuer)
paths = json.loads((source / "inputs.json").read_text(encoding="utf-8"))["paths"]
shares = data["shanghai_shares"] + data["hong_kong_shares"]
assert shares == round(issuer.SHARES * 1_000_000)


def hkd(cny, cny_per_hkd):
    return cny / cny_per_hkd


def calculate(changes):
    parameters = issuer.configured(changes)
    run = issuer.resource_asset_run(parameters)
    assert run["status"] == "computed_conditional"
    assert abs(run["reference_resource_conservation_error"]) < 1e-6
    assert abs(run["cash_to_asset_bridge"]["reconciliation_error"]) < 1e-5
    fx = data["cny_per_hkd"]
    dividends = [hkd(v, fx) for v in run["distributions_per_share"]]
    terminal = hkd(run["year5_value_per_share"], fx)
    current = hkd(run["current_value_per_share"], fx)
    factor = 1 + parameters["discount"]
    pv_distributions = sum(v / factor**i for i, v in enumerate(dividends, 1))
    assert math.isclose(current, pv_distributions + terminal / factor**5, abs_tol=1e-7)
    return {
        "current": current, "distributions": dividends, "year_5": terminal,
        "terminal_pv_share": terminal / factor**5 / current,
    }


assert hkd(80, 0.8) == 100
fixture = issuer.capital_fixtures()["no_legal_profit_but_known_capital"]
assert math.isclose(fixture["value"], 95 / 1.1**2)
runs = {
    "structural_bear": calculate(paths["A_permanent_weak"]),
    "cyclical_bear": calculate(paths["A_low"] | data["cyclical_changes_from_A_low"]),
    "base_low": calculate(paths["A_low"]),
    "base_high": calculate(paths["A_high"]),
    "bull": calculate(paths["B_high"]),
}
anchors = {name: round(run["current"], 2) for name, run in runs.items()}
assert list(anchors.values()) == sorted(anchors.values())
low, high = runs["base_low"], runs["base_high"]
assert low["distributions"] == high["distributions"]
auxiliary = {}
for side, args in data["auxiliary_arguments"].items():
    estimate = issuer.cash_power_crosscheck(**args)
    auxiliary[side] = round(hkd(estimate["current_value_per_share"], data["cny_per_hkd"]), 2)

retained = (1 - data["issuer_withholding"]) * (1 - data["clearing_withholding"])
result = {
    "symbol": "HK:00883", "report_period": "2026-Q3",
    "value_range": {"low": anchors["base_low"], "high": anchors["base_high"], "currency": "HKD"},
    "return_model": {
        "schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
        "model_as_of": data["as_of"],
        "base_case_distributions_per_share": [round(x, 6) for x in low["distributions"]],
        "base_case_terminal_equity_value_range_per_share": {
            "year_5": {"low": round(low["year_5"], 6), "high": round(high["year_5"], 6)}
        },
    },
    "scenarios": anchors | {"currency": "HKD", "horizon_note": "四组情景均为当前每股港元税前权益。结构承压采用长期低油价和较高资源成本，周期承压于第三年起恢复投入，较乐观情景按较高效率开发并逐步返还合格超额资金。"},
    "paths_hkd": runs, "auxiliary_hkd": auxiliary, "ordinary_shares": shares,
    "southbound_dividend_tax_rate": round(1 - retained, 2),
    "historical_dividend_hkd_after_withholding": round(data["dividend_hkd"] * retained, 4),
    "projected_southbound_dividends_hkd": [round(x * retained, 4) for x in low["distributions"]],
}
print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
