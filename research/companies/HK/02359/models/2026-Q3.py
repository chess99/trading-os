"""按香港上市普通股计量药明康德的经营分配及剩余权益。运行 python 2026-Q3.py。"""
import json
import math
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent


def value_in_hkd(cny, exchange_rate):
    return cny / exchange_rate


def calculate(data):
    relative_engine = Path(data["issuer_engine"])
    engine = next(parent / relative_engine for parent in HERE.parents if (parent / relative_engine).is_file())
    issuer = runpy.run_path(str(engine))
    issuer["tests"]()
    paths = issuer["scenarios"]()
    base = paths["base"]
    issued = sum(row["issued"] for row in data["share_classes"].values())
    treasury = sum(row["treasury"] for row in data["share_classes"].values())
    assert round(base["parameters"]["shares"] * 1e9) == issued
    fx = data["cny_per_hkd"]
    assert value_in_hkd(2, 0.8) == 2.5

    def convert(series, digits=2):
        return [round(value_in_hkd(value, fx), digits) for value in series]

    low, high = convert(base["current_value"])
    terminal_low, terminal_high = convert(base["terminal_year5"], 4)
    payouts = convert(base["distributions"], 5)
    for index, discount in enumerate((0.105, 0.095)):
        holder_pv = sum(value / (1 + discount) ** year for year, value in enumerate(payouts, 1))
        holder_pv += (terminal_low, terminal_high)[index] / (1 + discount) ** 5
        assert math.isclose(holder_pv, (low, high)[index], abs_tol=0.006)
    assert all(paths[label]["feasible"] for label in ("base", "upside", "structural", "cyclical"))
    scenario_ranges = {name: convert(paths[name]["current_value"]) for name in (
        "structural", "cyclical", "base", "upside", "capital_intensity", "upstream_delay_3", "old_losses_budget"
    )}
    anchors = dict(structural_bear=scenario_ranges["structural"][0], cyclical_bear=scenario_ranges["cyclical"][0],
                   base_low=low, base_high=high, bull=scenario_ranges["upside"][1],
                   currency="HKD", horizon_note=data["scenario_note"])
    assert 0 <= anchors["structural_bear"] <= anchors["cyclical_bear"] <= low <= high <= anchors["bull"]
    historical = data["interim_dividend"]
    assert round(historical["declared_per_share_cny"] * historical["hkd_per_cny_for_payment"], 3) == historical["default_hkd_per_share"]
    return {
        "symbol": "HK:02359", "report_period": "2026-Q3", "information_cutoff": data["information_cutoff"],
        "value_range": {"low": low, "high": high, "currency": "HKD"},
        "return_model": {
            "schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
            "model_as_of": data["information_cutoff"], "base_case_distributions_per_share": payouts,
            "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": terminal_low, "high": terminal_high}},
        },
        "scenarios": anchors, "scenario_ranges_hkd": scenario_ranges, "auxiliary_value_hkd": convert(base["auxiliary_value"]),
        "issuer_shares": {"issued": issued, "treasury": treasury, "ex_treasury": issued - treasury},
        "gross_to_personal_cash_hkd_equivalent": [
            round(x / fx * (1 - historical["southbound_personal_tax_rate"]), 4) for x in base["distributions"]
        ],
        "fx_sensitivity": {str(round(fx * change, 5)): [round(x / (fx * change), 2) for x in base["current_value"]]
                           for change in (0.95, 1.05)},
        "terminal_pv_fraction": [round(x, 4) for x in base["terminal_pv_share"]],
    }


if __name__ == "__main__":
    inputs = json.loads((HERE / "2026-Q3-input.json").read_text())
    result = calculate(inputs)
    (HERE / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
