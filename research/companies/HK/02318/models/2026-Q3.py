"""重算中国平安 H 股价值。人民币经营路径与 A 股共用，港币按人民币/港币换算。"""
import json
import math
import runpy
from pathlib import Path


def evaluate(inputs, engine):
    fx = inputs["cny_per_hkd"]
    fx_value = lambda amount, digits=2: round(amount / fx, digits)
    project = engine["projection"]
    base = engine["BASE"]
    paths = inputs["cases"]
    issued = inputs["issued_a"] + inputs["issued_h"] - inputs["treasury_a_and_h"]
    assert math.isclose(issued / 1e9, engine["SH"])
    paid = inputs["interim_dividend_cny"]
    old_h_payment = inputs["issued_h"] * paid / 1e9
    assert math.isclose(old_h_payment, 7.29862537376)
    assert abs(paid * inputs["interim_hkd_per_cny"] - inputs["interim_default_hkd"]) < 0.00001

    variants = {
        "structural_bear": paths["structural"],
        "cyclical_bear": paths["core_low"] | paths["cyclical_overlay_on_low"],
        "base_low": paths["core_low"],
        "base_high": paths["core_high"],
        "bull": paths["bull"],
        "mid": {},
        "alternative_low": paths["core_low"] | {"ev_emergence": True},
        "alternative_high": paths["core_high"] | {"ev_emergence": True},
    }
    results = {key: project(base | change) for key, change in variants.items()}
    for result in results.values():
        assert math.isclose(result["value"], engine["present"](
            result["distributions"], result["params"]["cost"], result["tv5"]
        ))
    # 同一折现函数的手算检验：10%贴现下，年付10、第五年末剩余100的价值为100。
    assert math.isclose(engine["present"]([10] * 5, .10, 100), 100)
    mid = results["mid"]
    delayed = project(base | {"delay": .5})["rows"][0]
    first = mid["rows"][0]
    assert math.isclose(first["parent_cash"] - delayed["parent_cash"], first["parent_declared"] / 2)
    assert math.isclose(first["parent_legal"], delayed["parent_legal"])
    values = {key: fx_value(results[key]["value"]) for key in (
        "structural_bear", "cyclical_bear", "base_low", "base_high", "bull"
    )}
    assert list(values.values()) == sorted(values.values())
    return {
        "symbol": inputs["symbol"], "report_period": inputs["report_period"],
        "value_range": {"low": values["base_low"], "high": values["base_high"], "currency": "HKD"},
        "scenarios": {"currency": "HKD", **values, "horizon_note": "四条路径均由同一时点税前普通股分配折现，周期弱情景在核心低端长期经营水平上叠加三年暂时性利润冲击和前两年收款延迟。"},
        "return_model": {
            "schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
            "model_as_of": inputs["information_cutoff"],
            "base_case_distributions_per_share": [fx_value(d, 4) for d in mid["distributions"]],
            "base_case_terminal_equity_value_range_per_share": {"year_5": {
                "low": fx_value(results["base_low"]["tv5"]), "high": fx_value(results["base_high"]["tv5"])
            }}
        },
        "alternative_low_high_hkd": [fx_value(results[k]["value"]) for k in ("alternative_low", "alternative_high")],
        "terminal_pv_fraction_low_high": [round(results[k]["tv5_pv_share"], 4) for k in ("base_low", "base_high")],
        "mid_hkd": fx_value(mid["value"]),
        "weak_distributions_hkd": [fx_value(d) for d in results["cyclical_bear"]["distributions"]],
        "starting_share_count": issued,
        "modeled_diluted_shares": round(first["shares"] * 1e9),
        "h_interim_dividend_already_deducted_cny_billion": round(old_h_payment, 6)
    }


if __name__ == "__main__":
    folder = Path(__file__).resolve().parent
    inputs = json.loads((folder / "2026-Q3-input.json").read_text())
    engine_file = next(p / inputs["issuer_engine"] for p in folder.parents if (p / inputs["issuer_engine"]).exists())
    output = evaluate(inputs, runpy.run_path(str(engine_file)))
    (folder / "2026-Q3-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
