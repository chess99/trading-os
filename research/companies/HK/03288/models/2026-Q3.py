"""海天味业 H 股。运行 python 2026-Q3.py，以港元输出估值与分配。"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
inputs = json.loads((HERE / "2026-Q3-input.json").read_text())
issuer = next(parent / inputs["issuer_model_path"] for parent in HERE.parents
              if (parent / inputs["issuer_model_path"]).is_dir())
sys.dont_write_bytecode = True
sys.path.insert(0, str(issuer / "2026-Q3"))
import baseline
import cash_replay


def capital_event(data):
    trades = data["post_quarter_repurchases"]
    a_count = sum(t["a_shares"] for t in trades)
    h_pending = data["q3_h_pending"] + sum(t["h_shares"] for t in trades)
    h_cny = sum(t["h_cash_hkd"] * t["cny_per_hkd"] for t in trades)
    return {
        "bought_increment_shares": a_count,
        "paid_increment_CNY": sum(t["a_cash_cny"] for t in trades),
        "h_issuer_held_excluded_shares": h_pending,
        "h_increment_cash_RMB_condition": h_cny * data["settlement_fx_multiplier"] * (1 + data["h_fee_budget"]),
    }


def calculate(data):
    fx = data["cny_per_hkd"]

    def hkd(amount):
        return round(amount / fx, 4)

    simple = dict(q3_h_pending=1, settlement_fx_multiplier=1, h_fee_budget=0,
                  post_quarter_repurchases=[dict(a_shares=2, a_cash_cny=10, h_shares=3,
                                                  h_cash_hkd=20, cny_per_hkd=0.8)])
    assert capital_event(simple) == dict(bought_increment_shares=2, paid_increment_CNY=10,
                                         h_issuer_held_excluded_shares=4, h_increment_cash_RMB_condition=16)
    event = capital_event(data)
    a_treasury = data["q3_a_treasury"] + event["bought_increment_shares"]
    h_pending = event["h_issuer_held_excluded_shares"]
    assert (a_treasury, h_pending) == (data["last_reported_a_treasury"], data["last_reported_h_pending"])
    entitled = data["issued_a"] + data["issued_h"] - a_treasury - h_pending
    assert math.isclose(entitled / 1e9, cash_replay.SHARES - (event["bought_increment_shares"] + h_pending) / 1e9)
    configs = json.loads((issuer / "2026-Q3-input.json").read_text())["financial_inputs"]["cases"]
    scenarios = list(configs)
    for name in ("cycle", "structural", "upside"):
        overrides = data["cycle_overrides"] if name == "cycle" else {}
        scenarios.append(dict(method="product", scenario=name, years=360, parameters=overrides))
    paths = {}
    for spec in scenarios:
        method, name = spec["method"], spec["scenario"]
        options = dict(n=spec["years"], override=spec["parameters"])
        operating = baseline.run(method, name, **options)
        path = cash_replay.run(method, name, operating, event, **options)
        assert path["feasible"] and len(path["years"]) == spec["years"], name
        discount = 1 + path["assumptions"]["r"]
        pv5 = sum(d / discount**i for i, d in enumerate(path["distributions"], 1))
        assert math.isclose(pv5 + path["terminal_year5"] / discount**5, path["value_per_share"])
        paths[method, name] = path

    def current(name, method="product"):
        return hkd(paths[method, name]["value_per_share"])

    anchors = dict(currency="HKD", structural_bear=current("structural"), cyclical_bear=current("cycle"),
                   base_low=current("core_low"), base_high=current("core_high"), bull=current("upside"))
    numbers = [anchors[name] for name in ("structural_bear", "cyclical_bear", "base_low", "base_high", "bull")]
    assert numbers == sorted(numbers)
    base = paths["product", "base"]
    terminal = {}
    for case in ("low", "high"):
        branch = paths["product", "terminal_" + case]
        assert branch["distributions"] == base["distributions"]
        terminal[case] = hkd(branch["terminal_year5"])
    holder = dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD",
                  model_as_of=data["cutoff"], base_case_distributions_per_share=list(map(hkd, base["distributions"])),
                  base_case_terminal_equity_value_range_per_share={"year_5": terminal})
    return dict(symbol="HK:03288", report_period=data["report_period"],
                value_range=dict(low=anchors["base_low"], high=anchors["base_high"], currency="HKD"),
                return_model=holder, scenarios=anchors, entitled_shares=entitled, capital_event=event,
                main_mid=current("base"), channel_range=[current(n, "channel") for n in ("core_low", "base", "core_high")],
                year_5_terminal_pv_share=round(base["terminal_pv_share"], 5),
                projected_shares_billion=[round(y["economic_shares"], 7) for y in base["years"][:5]],
                remaining_a_plan_cny=round(245306554.64 - event["paid_increment_CNY"], 2))


if __name__ == "__main__":
    print(json.dumps(calculate(inputs), ensure_ascii=False, allow_nan=False, indent=2))
