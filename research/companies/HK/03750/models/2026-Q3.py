"""宁德时代 H 股：逐日滚存真实回购，复用发行人经营、资本及母公司支付模型。"""
from datetime import date
from decimal import Decimal
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True


def hkd(amount, cny_per_hkd, places=2):
    return round(amount / cny_per_hkd, places)


def main():
    facts = json.loads((HERE / "2026-Q3-input.json").read_text())
    relative = Path(facts["issuer_engine"])
    source = next(p / relative for p in HERE.parents if (p / relative).is_file())
    assert sha256(source.read_bytes()).hexdigest() == facts["issuer_engine_sha256"]
    loader = spec_from_file_location("issuer_q3", source)
    engine = module_from_spec(loader)
    loader.loader.exec_module(engine)
    fx = facts["hkd_to_cny"]
    quarter_end = date.fromisoformat(facts["fiscal_end"])
    elapsed = (date.fromisoformat(facts["information_cutoff"][:10]) - quarter_end).days
    trades = facts["november_buybacks"]
    total_order_cash = sum(Decimal(t["consideration_rmb"]) for t in trades)
    nov_shares = sum(t["shares"] for t in trades)
    assert [t["trade_date"] for t in trades] == sorted({t["trade_date"] for t in trades})
    assert round((engine.SEPT_QTY + sum(t[1] for t in engine.TRADES)) * 1e9) == facts["october_pending"]
    for t in trades:
        days = (date.fromisoformat(t["trade_date"]) - quarter_end).days
        assert 31 < days <= elapsed
        engine.TRADES.append((days, t["shares"] / 1e9, float(t["consideration_rmb"]) / 1e9))

    participating = facts["registered_a"] + facts["registered_h"] - facts["employee_treasury"] - facts["october_pending"] - nov_shares
    assert math.isclose(engine.REGISTERED * 1e9, facts["registered_a"] + facts["registered_h"])
    assert round(engine.EMPLOYEE * 1e9) == facts["employee_treasury"]
    assert hkd(1.5, 0.75) == 2
    assert engine.law(1, 0, 8, 10) == (10, 1, 1, 0)

    def evaluate(method, params):
        model = engine.run(method=method, cutday=elapsed, trade_through=elapsed, n_years=300, **params)
        assert model["feasible"] and model["tail_PV_upper_bound"] / fx < 0.0001
        assert round(model["capital_bridge"]["actual_effective_shares"] * 1e9) == participating
        rows = model["rows"]
        assert all(min(row["parent_cash"], row["source_cash"], row["parent_retained"]) >= -1e-7 for row in rows)
        dps = model["D"]
        discount = 1 + params["r"]
        present = sum(d / discount ** t for t, d in enumerate(dps, 1)) + model["TV5"] / discount ** 5
        assert math.isclose(present, model["PV"], rel_tol=1e-12)
        return {"pv_hkd": hkd(model["PV"], fx), "year_5_hkd": hkd(model["TV5"], fx),
                "cash_hkd": [hkd(d, fx, 4) for d in dps],
                "year_5_pv_share": round(model["TV_fraction"], 4),
                "effective_shares_year_1_to_5": [round(row["effective_dividend_budget_shares"] * 1e9) for row in rows[:5]]}

    volume = {name: evaluate("volume", p) for name, p in facts["paths"].items()}
    profits = {name: evaluate("earnings", facts["paths"][name]) for name in ("core_low", "base", "core_high")}
    scenarios = {field: volume[case]["pv_hkd"] for field, case in [
        ("structural_bear", "structural"), ("cyclical_bear", "cyclical"), ("base_low", "core_low"),
        ("base_high", "core_high"), ("bull", "bull")]}
    assert list(scenarios.values()) == sorted(scenarios.values())
    assert volume["core_low"]["cash_hkd"] == volume["base"]["cash_hkd"] == volume["core_high"]["cash_hkd"]
    holder = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
              "model_as_of": facts["information_cutoff"], "base_case_distributions_per_share": volume["base"]["cash_hkd"],
              "base_case_terminal_equity_value_range_per_share": {"year_5": {
                  "low": volume["core_low"]["year_5_hkd"], "high": volume["core_high"]["year_5_hkd"]}}}
    fund = facts["hong_kong_fund"]
    max_bn = fund["usd_limit"] * fund["cny_per_usd"] / 1e9
    calls = [max_bn * weight for weight in fund["years_one_to_three_call_weights"]]
    assert math.isclose(sum(calls), max_bn)
    # Y1产业净投入20亿元中已有4亿元国内基金，另两年总净投入分别440、450亿元。
    assert calls[0] + 0.4 < 2 and calls[1] < 44 and calls[2] < 45
    # 最严单项压力：在已有资本预算之外，再从非母资金立即隔离全额承诺，回收为零。
    # 扣除9月末至截止日的预算利息，令截止日现金的差值恰为全额认缴。
    engine.FIN -= max_bn / (1 + .02 * elapsed / 365)
    fund_loss = evaluate("volume", facts["paths"]["base"])["pv_hkd"]
    result = {"symbol": facts["symbol"], "report_period": facts["report_period"],
              "information_cutoff": facts["information_cutoff"],
              "value_range": {"low": scenarios["base_low"], "high": scenarios["base_high"], "currency": "HKD"},
              "return_model": holder, "scenarios": {"currency": "HKD", **scenarios, "horizon_note": "各路径均为当期每股港元价值，采用相同回购、分红权与母公司支付规则。"},
              "volume": volume, "earnings": profits, "shares_eligible": participating,
              "pending_cancellation": facts["october_pending"] + nov_shares, "november_shares": nov_shares,
              "november_consideration_cny": str(total_order_cash),
              "hong_kong_fund": {"commitment_cny_bn": round(max_bn, 5),
                                 "annual_calls_inside_existing_capital_budget_cny_bn": [round(v, 5) for v in calls],
                                 "full_incremental_loss_base_pv_hkd": fund_loss}}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
