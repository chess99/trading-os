"""执行 python 2026-Q3.py，在本文件旁生成港股税前价值、未来分配和资本事件对照。"""
import argparse
import hashlib
import json
from pathlib import Path
from types import ModuleType

DIR = Path(__file__).resolve().parent
INPUT = json.loads((DIR / "2026-Q3-input.json").read_text())


def load_engine():
    relative = Path(INPUT["issuer_engine"])
    path = next(parent / relative for parent in DIR.parents if (parent / relative).is_file())
    source = path.read_bytes()
    assert hashlib.sha256(source).hexdigest() == INPUT["issuer_engine_sha256"]
    engine = ModuleType("issuer_engine")
    exec(compile(source, str(path), "exec"), engine.__dict__)
    return engine


def capital_bridge(issued, reserve_project=True):
    """交易均按全资子公司对集团母公司的经济权益归集，人民币十亿元。"""
    engine = load_engine()
    fx = INPUT["cny_per_hkd"]
    shares = INPUT["a_shares"] + INPUT["h_shares"]
    assert abs(engine.SHARES - shares / 1e9) < 1e-10
    capital = INPUT["placing_net_hkd_bn"] * fx if issued else 0
    debt_repayment = capital * INPUT["placing_debt_fraction"]
    project = (INPUT["project_budget_cny_bn"] - INPUT["project_spent_march_cny_bn"]) * INPUT["incremental_project_share"] if reserve_project else 0
    reserved = INPUT["acquisition_cash_cny_bn"] + project
    engine.INITIAL["pc"] += capital - debt_repayment - reserved
    engine.INITIAL["pd"] -= debt_repayment
    if issued:
        shares += INPUT["placing_shares"]
    engine.SHARES = shares / 1e9
    # 登记资本取新股登记完成后的面值上界；母公司公积仍超过一半。
    engine.REGISTERED = engine.SHARES
    assert engine.P_RESERVE >= engine.REGISTERED / 2
    net_change = capital - reserved
    assert abs(engine.INITIAL["pc"] - engine.INITIAL["pd"] - (45.426 - 52.8) - net_change) < 1e-9
    return engine, net_change


def run():
    fx = INPUT["cny_per_hkd"]
    engine, change = capital_bridge(True)
    engine.fixtures()
    cases = {k: engine.run(**parameters) for k, parameters in INPUT["assumptions"].items()}
    scenario_keys = ["structural_bear", "cyclical_bear", "base_low", "base_high", "bull"]
    anchors = {k: round(cases[k]["value"] / fx, 2) for k in scenario_keys}
    assert list(anchors.values()) == sorted(anchors.values()) and min(anchors.values()) >= 0
    cash = cases["base"]["distributions"]
    terminal = {k: round(cases["holder_" + k]["year5_terminal"] / fx, 6) for k in ("low", "high")}
    for k in ("low", "high"):
        holder = cases["holder_" + k]
        rate = holder["parameters"]["r"]
        assert abs(engine.pv(cash, rate) + holder["year5_terminal"] / (1 + rate)**5 - holder["value"]) < 1e-10
    # 同一发行人未杠杆现金年金法原始权益加期初资金增减，再按新分母计价。
    original = load_engine()
    annuity = original.build()["method2"]["values"]
    second = {str(r): round((annuity[str(r)] * original.SHARES + change) / engine.SHARES / fx, 2) for r in (0.085, 0.08, 0.075)}
    sensitivity = {}
    for label, complete, reserve in (("without_placing", False, True), ("without_incremental_project_reserve", True, False)):
        other, _ = capital_bridge(complete, reserve)
        sensitivity[label] = {k: round(other.run(**INPUT["assumptions"][k])["value"] / fx, 2) for k in ("base_low", "base", "base_high")}
    return {
        "symbol": "HK:01088", "report_period": "2026-Q3", "information_cutoff": INPUT["model_as_of"],
        "value_range": {"low": anchors["base_low"], "high": anchors["base_high"], "currency": "HKD"},
        "return_model": {
            "schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
            "model_as_of": INPUT["model_as_of"], "base_case_distributions_per_share": [round(x / fx, 6) for x in cash],
            "base_case_terminal_equity_value_range_per_share": {"year_5": terminal}
        },
        "scenarios": {"currency": "HKD", **anchors, "horizon_note": "代表同一时点每股普通股税前价值。基准假设配售交割并保留新增煤制气建设资金，情景联动调整经营寿命、资本付款与资金成本。"},
        "base_mid_hkd": round(cases["base"]["value"] / fx, 2),
        "year5_terminal_pv_fraction": round(cases["base"]["terminal_pv_share"], 4),
        "project_incremental_reserve_cny_bn": round((INPUT["project_budget_cny_bn"] - INPUT["project_spent_march_cny_bn"]) * INPUT["incremental_project_share"], 3),
        "issued_shares_at_cutoff": INPUT["a_shares"] + INPUT["h_shares"], "conditional_shares_after_placing": round(engine.SHARES * 1e9),
        "auxiliary_annuity_hkd": second, "sensitivity_hkd": sensitivity
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DIR / "2026-Q3-output.json")
    parser.parse_args().output.write_text(json.dumps(run(), ensure_ascii=False, indent=2, allow_nan=False) + "\n")
