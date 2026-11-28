"""运行 python 2026-Q3.py，使用同发行人的人民币现金流模型重算每股港元结果。"""
import argparse
import json
import math
import runpy
from pathlib import Path


HERE = Path(__file__).resolve().parent


def translate(cny_per_share, cny_per_hkd):
    return cny_per_share / cny_per_hkd


def build(inputs):
    root = next(folder for folder in HERE.parents if (folder / inputs["issuer_model"]).is_file())
    engine = runpy.run_path(str(root / inputs["issuer_model"]))
    engine["literal_tests"]()
    security = inputs["security"]
    shares = security["issued_a"] + security["issued_h"]
    treasury = security["current_a_treasury"]
    purchases = inputs["november_purchases"]
    assert sum(r["shares"] for r in purchases) + security["october_a_treasury"] == treasury
    diluted = shares + security["h_share_scheme_ceiling"]
    spent = sum(r["cost_cny"] for r in purchases) / 1e9
    fx = inputs["cny_per_hkd"]
    tax = inputs["southbound_dividend_tax"]
    assert translate(2, 0.8) == 2.5
    assert math.isclose(translate(0.20, inputs["last_dividend"]["cny_per_hkd"]),
                        inputs["last_dividend"]["gross_hkd"], abs_tol=0.00001)

    def update(params):
        assert math.isclose(params["shares"] * 1e9, diluted, abs_tol=0.01)
        # 已支付的员工计划购股款移出期初现金，并减少尚需支付的预算。
        # 母公司是买方，两本账都扣现金。未来员工缴款仍按原计划总量预算。
        old_net_cash = params["cash"] - params["employee_payment"]
        params["cash"] -= spent
        params["parent_cash"] -= spent
        params["employee_payment"] -= spent
        assert math.isclose(params["cash"] - params["employee_payment"], old_net_cash)
        return params

    paths = engine["all_parameters"]()
    weak = paths["cyclical_weak"]
    weak["k"] = inputs["weak_case"]["discount_rate"]
    weak["g"] = inputs["weak_case"]["perpetual_growth"]
    results = {name: engine["simulate"](update(p)) for name, p in paths.items()}
    sensitivities = engine["sensitivities"]()
    terminal = [engine["simulate"](update(sensitivities[name]))["year5_terminal_per_share"]
                for name in ("return_terminal_low", "return_terminal_high")]
    base = results["base"]
    aux = engine["auxiliary"](base)
    distributions = [round(translate(x, fx), 6) for x in base["base_case_distributions_per_share"]]
    values = [round(translate(results[name]["value_per_share"], fx), 2) for name in
              ("structural_adverse", "cyclical_weak", "core_low", "core_high", "optimistic")]
    assert 0 <= values[0] and values == sorted(values)
    value_range = dict(low=values[2], high=values[3], currency="HKD")
    anchors = dict(zip(("structural_bear", "cyclical_bear", "base_low", "base_high", "bull"), values))
    anchors.update(currency="HKD", horizon_note="各情景均为当前每股港元普通股权益；周期承压保留新品恢复与再投资，结构承压削弱长期毛利与授权能力，并约束资金上划。")
    return_model = dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD",
                        model_as_of=inputs["as_of"], base_case_distributions_per_share=distributions,
                        base_case_terminal_equity_value_range_per_share={"year_5": {
                            "low": round(translate(terminal[0], fx), 6),
                            "high": round(translate(terminal[1], fx), 6)}})
    return dict(symbol="HK:01276", report_period="2026-Q3", value_range=value_range, scenarios=anchors,
                return_model=return_model, southbound_net_distributions=[round(x*(1-tax), 6) for x in distributions],
                issued_shares=shares, current_dividend_eligible_shares=shares-treasury, diluted_shares=diluted,
                november_purchases_cny=round(spent*1e9, 2), remaining_employee_purchase_budget_cny_bn=base["parameters"]["employee_payment"],
                auxiliary_range_hkd=[round(translate(aux[key], fx), 2) for key in ("low", "high")],
                central_value_hkd=round(translate(base["value_per_share"], fx), 2),
                post_year10_pv_weight=round(base["post_year10_pv_fraction"], 4),
                post_year50_pv_weight=round(base["terminal_pv_fraction"], 4))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "2026-Q3-output.json")
    result = build(json.loads((HERE / "2026-Q3-input.json").read_text()))
    parser.parse_args().output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
