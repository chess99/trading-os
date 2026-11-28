"""由同发行人三季报普通股引擎生成 H 股税前价值，直接运行写入同目录结果。"""
import json
import runpy
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT = json.loads((HERE / "2026-Q3-input.json").read_text())
ENGINE = next(p / INPUT["issuer_engine"] for p in HERE.parents if (p / INPUT["issuer_engine"]).is_file())
ISSUER = runpy.run_path(str(ENGINE))


def to_hkd(cny, rate):
    return cny / rate


def main():
    fx = INPUT["cny_per_hkd"]
    entitled = INPUT["a_shares"] + INPUT["h_shares"] - INPUT["treasury"]
    assert isclose(entitled / 1e9, ISSUER["SHARES"], abs_tol=1e-10)
    assert isclose(to_hkd(fx, fx), 1)
    # 法人分配特例：期初亏损 2，本年净利 12，弥亏后提储备 1，最多分 9。
    retained, reserve, paid, _, _ = ISSUER["reserve_and_distribution"](-2, 0, 12, 100, 20, 20, 0)
    assert (retained, reserve, paid) == (0, 1, 9)

    run = ISSUER["run"]
    paths = {name: run(*params) for name, params in INPUT["scenario_inputs"].items()}
    base, second = run(), run("capital")
    scenarios = {name: round(to_hkd(case["value"], fx), 2) for name, case in paths.items()}
    assert list(scenarios.values()) == sorted(scenarios.values())
    core = {key: scenarios["base_" + key] for key in ("low", "high")}
    terminal = {}
    for key, rate in (("low", 0.105), ("high", 0.095)):
        holder = run("base", rate)
        assert holder["distributions"] == base["distributions"]
        terminal[key] = round(to_hkd(holder["terminal_y5"], fx), 2)
        pv = sum(d / (1 + rate)**y for y, d in enumerate(holder["distributions"], 1))
        assert isclose(pv + holder["terminal_y5"] / (1 + rate)**5, holder["value"])
    distributions = [round(to_hkd(d, fx), 6) for d in base["distributions"]]
    result = {
        "symbol": "HK:01211",
        "report_period": "2026-Q3",
        "information_cutoff": INPUT["cutoff"],
        "value_range": {**core, "currency": "HKD"},
        "return_model": {
            "schema_version": 1, "method": "annual_common_equity_irr_v1",
            "currency": "HKD", "model_as_of": INPUT["cutoff"],
            "base_case_distributions_per_share": distributions,
            "base_case_terminal_equity_value_range_per_share": {"year_5": terminal},
        },
        "scenarios": {"currency": "HKD", **scenarios,
            "horizon_note": "税前每股港元现值。结构弱情景削减汽车利润率并永久降低子公司上划能力，周期弱情景压低前三年销量、利润率和周转速度。较乐观路径提高汽车利润率并沿用资本、税与母公司分配约束。"},
        "entitled_ordinary_shares": entitled,
        "primary_central_hkd": round(to_hkd(base["value"], fx), 2),
        "secondary_method_hkd": round(to_hkd(second["value"], fx), 2),
        "terminal_pv_share": round(base["tail_pv_after_y5"] / base["value"], 4),
        "fx_sensitivity": {
            str(round(fx * multiple, 5)): {
                key: round(to_hkd(paths["base_" + key]["value"], fx * multiple), 2)
                for key in ("low", "high")
            } for multiple in (0.95, 1.05)
        },
    }
    (HERE / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
