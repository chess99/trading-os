"""用发行人经营模型重算美的 H 股。直接运行本文件会写入同目录的周期结果。"""
from copy import deepcopy
import importlib.util
import json
from math import isclose
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "2026-Q3-input.json").read_text())
ENGINE = next(root / DATA["issuer_engine"] for root in HERE.parents if (root / DATA["issuer_engine"]).is_file())
spec = importlib.util.spec_from_file_location("midea_issuer", ENGINE)
issuer = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(issuer)
BILLION = 1_000_000_000


def hkd(value, cny_per_hkd):
    return value / cny_per_hkd


def opening():
    d = DATA
    start = issuer.initial(issuer.DEFAULT)
    parent, clou = start["P"], start["C"]
    registered = d["a_registered"] + d["h_registered"]
    treasury = d["a_treasury"] + d["h_treasury"]
    entitled = registered - treasury
    options_exercised = d["a_registered"] + d["restricted_cancel_shares"] - d["september_a_registered"]
    options_remaining = d["september_option_shares"] - options_exercised
    option_cash = options_exercised * d["option_price_cny"] / BILLION
    repurchase = (d["market_repurchase_to_nov_cny"] - d["market_repurchase_to_sep_cny"] + d["restricted_cancel_cash_cny"]) / BILLION
    dividend = entitled * d["interim_dividend_cny"] / BILLION
    received = d["clou_cash_received_cny"] / BILLION
    # 派现同时占用法定留存。登记日已锁定的 A 股应付先从可用现金预留。
    parent["cash"] = issuer.FACT["parent_cash"] + option_cash - repurchase - dividend - received
    parent["re"] -= dividend
    parent["perpetual_cost"] += received
    parent["perpetual_tax_basis"] += received
    clou["cash"] += received
    clou["perpetual"] += received
    # 到账属事实，具体偿债进度未知。基准沿用发行人的资金用途预算。
    repayment = min(received, clou["bank"])
    clou["bank"] -= repayment
    clou["cash"] -= repayment
    start["registered"] = registered / BILLION
    start["treasury"] = treasury / BILLION
    # 发行人代码按这两项之和模拟将已购库存股注销；注销不改变享权股数。
    issuer.FACT["oct_buy_shares"] = (d["market_repurchase_to_nov_shares"] / BILLION
                                      - issuer.FACT["cancel_treasury_sep"])
    adjustments = {"option_shares": options_remaining / BILLION, "clou_support": 0.0}
    assert entitled == 7_416_598_731
    assert isclose(parent["cash"] + clou["cash"] + repayment,
                   issuer.FACT["parent_cash"] + 0.5 + option_cash - repurchase - dividend)
    bridge = dict(registered=registered, treasury=treasury, entitled=entitled, exercised=options_exercised,
                  remaining_options=options_remaining, new_option_cash_bn=option_cash, repurchase_bn=repurchase,
                  dividend_reserved_or_paid_bn=dividend, clou_funded_bn=received,
                  available_parent_cash_bn=parent["cash"], parent_retained_earnings_bn=parent["re"])
    return start, adjustments, bridge


def main():
    start, adjustments, bridge = opening()
    fx = DATA["cny_per_hkd"]
    def run(params, *, initial=start, first_year=1):
        result = issuer.project(dict(adjustments, **params), start=initial, startyear=first_year)
        assert result["all_feasible"], params
        return result

    cases = {
        "structural_bear": {"structural": True, "working_capital_shock": 15., "clou_margin_end": -.02},
        "cyclical_bear": {"cyclical": True, "working_capital_shock": 8.},
        "base_low": {"margin_shift": -.0025, "growth_scale": .85, "k": .09},
        "base_high": {"margin_shift": .0025, "growth_scale": 1.10, "k": .08},
        "bull": {"growth_scale": 1.35, "margin_shift": .006},
    }
    anchors = {name: round(hkd(run(p)["pv_per_share"], fx), 2) for name, p in cases.items()}
    assert sorted(anchors.values()) == list(anchors.values())
    base = run({})
    rows = base["years"]
    ds = [hkd(row["dps"], fx) for row in rows[:5]]
    y5 = rows[4]["end"]
    def terminal(k):
        return hkd(run({"k": k}, initial=y5, first_year=6)["pv_per_share"], fx)
    base_value = hkd(base["pv_per_share"], fx)
    terminal_share = terminal(.085) / 1.085**5 / base_value
    assert isclose(sum(v / 1.085**n for n, v in enumerate(ds, 1)) / base_value + terminal_share, 1.)
    assert isclose(hkd(4., .8), 5.)
    assert isclose(rows[0]["shares"], (bridge["entitled"] + bridge["remaining_options"]) / BILLION
                   + issuer.DEFAULT["employee_treasury_release"] / 4)
    def value(params):
        return round(hkd(run(params)["pv_per_share"], fx), 2)
    # 科陆尚未披露实际偿债额，独立重跑将整笔暂存子公司现金的情形。
    retained = deepcopy(start)
    retained["C"]["bank"] += bridge["clou_funded_bn"]
    retained["C"]["cash"] += bridge["clou_funded_bn"]
    result = {
        "symbol": "HK:00300", "report_period": "2026-Q3", "information_cutoff": DATA["cutoff"],
        "value_range": {"low": anchors["base_low"], "high": anchors["base_high"], "currency": "HKD"},
        "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
                         "model_as_of": DATA["cutoff"], "base_case_distributions_per_share": ds,
                         "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": terminal(.09), "high": terminal(.08)}}},
        "anchors_hkd": anchors, "base_hkd": round(base_value, 2), "second_method_hkd": value({"method": "reinvestment"}),
        "opening_bridge": bridge, "years_1_to_5_entitled_billions": [row["shares"] for row in rows[:5]],
        "terminal_pv_share": terminal_share, "slow_upstream_hkd": value({"upstream_payout": .60, "upstream_reserve_release": .025, "settlement_years": 24}),
        "clou_cash_retained_hkd": round(hkd(run({}, initial=retained)["pv_per_share"], fx), 2),
        "core_fx_sensitivity_hkd": {str(rate): [round(hkd(anchors[k] * fx, rate), 2) for k in ("base_low", "base_high")] for rate in (.83, .88)},
    }
    (HERE / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
