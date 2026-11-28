"""青岛啤酒 H 股。运行本文件生成同目录简明结果。"""
import json
import runpy
from pathlib import Path


def evaluate(inputs, model):
    fx = inputs["cny_per_hkd"]
    shares = sum(inputs["share_classes"].values()) - inputs["treasury_shares"]
    assert shares == round(model["SHARES"] * 1e9)

    def hkd(cny):
        return cny / fx

    assert abs(hkd(fx * 10) - 10) < 1e-12
    assert round(inputs["last_payment"]["cny"] / inputs["last_payment"]["cny_per_hkd"], 2) == inputs["last_payment"]["hkd"]
    model["tests"]()
    cases = model["CASES"]
    selected = ["structural", "core_low", "core_high", "optimistic", "base", "aux_unit", "terminal_low", "terminal_high"]
    results = {key: model["run"](cases[key], rows=False) for key in selected}
    stress = inputs["cyclical_case"]
    results["cycle"] = model["run"](dict(cases[stress["steady_case"]], cycle=stress["cycle"]), rows=False)
    keys = ("structural_bear", "cyclical_bear", "base_low", "base_high", "bull")
    paths = ("structural", "cycle", "core_low", "core_high", "optimistic")
    anchors = {key: round(hkd(results[path]["value"]), 2) for key, path in zip(keys, paths)}
    assert list(anchors.values()) == sorted(anchors.values())
    dividends = results["base"]["distributions_5"]
    for key in ["terminal_low", "terminal_high"]:
        assert dividends == results[key]["distributions_5"]
    return {
        "symbol": "HK:00168", "report_period": "2026-Q3",
        "value_range": {"low": anchors["base_low"], "high": anchors["base_high"], "currency": "HKD"},
        "scenarios": {**anchors, "currency": "HKD", "horizon_note": "均为当前每股税前港元价值。结构压力持续损害利润率和需求，周期压力三年后回归核心低位；较乐观情景计入配套投资。"},
        "return_model": {
            "schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
            "model_as_of": inputs["as_of"],
            "base_case_distributions_per_share": [round(hkd(d), 4) for d in dividends],
            "base_case_terminal_equity_value_range_per_share": {
                "year_5": {k: round(hkd(results["terminal_" + k]["terminal_5"]), 2) for k in ("low", "high")}
            },
        },
        "base_present_value_hkd": round(hkd(results["base"]["value"]), 2),
        "unit_economics_present_value_hkd": round(hkd(results["aux_unit"]["value"]), 2),
        "year_5_terminal_fraction_of_base": round(results["base"]["terminal_pv_fraction"], 4),
        "eligible_shares": shares,
        "southbound_personal_dividend_tax": inputs["southbound_personal_dividend_tax"],
    }


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    inputs = json.loads((here / "2026-Q3-input.json").read_text())
    issuer_path = inputs["issuer_engine"]
    root = next(p for p in here.parents if (p / issuer_path).is_file())
    output = evaluate(inputs, runpy.run_path(str(root / issuer_path)))
    (here / "2026-Q3-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
