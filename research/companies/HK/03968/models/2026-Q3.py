"""复算招商银行每股 H 股税前所有权价值。运行 python 2026-Q3.py。"""

import hashlib
import json
from datetime import date
from math import isclose
from pathlib import Path
from runpy import run_path


def main():
    here = Path(__file__).resolve().parent
    data = json.loads((here / "2026-Q3-input.json").read_text())
    repo = next(p for p in here.parents if (p / data["issuer_model"]).is_file())
    for name in ("issuer_model", "issuer_input"):
        assert hashlib.sha256((repo / data[name]).read_bytes()).hexdigest() == data[name + "_sha256"]
    engine = run_path(str(repo / data["issuer_model"]))
    engine["self_test"]()
    issuer = engine["INPUT"]
    facts = issuer["facts"]
    shares = (data["issued_a_shares"] + data["issued_h_shares"] - data["treasury_shares"]) / 1e6
    assert isclose(shares, facts["shares_million"])
    assert facts["common_equity"] == data["equity_to_parent_rmb_million"] - data["other_equity_rmb_million"]
    days = (date.fromisoformat(data["cutoff"][:10]) - date.fromisoformat(data["period_end"])).days
    assert data["rmb_after_period_end_dividend_per_share"] == 0
    facts["stub_common_profit"] = facts["forecast_2026_common_profit"] * days / 365
    book = (facts["common_equity"] + facts["stub_common_profit"]) / shares
    fx = data["rmb_per_hkd"]

    def hkd(rmb, digits=2):
        return round(rmb / fx, digits)

    assert hkd(2 * fx) == 2
    path = engine["value_path"]
    base = path("base")
    ends = base["endpoints"]
    low, high = [hkd(e["value_per_share"]) for e in ends]
    dividends = [hkd(row["dividend"] / shares, 4) for row in base["rows"][:5]]
    scenario = {"currency": "HKD"}
    for name, key, ix in (("structural_bear", "structural", 0), ("cyclical_bear", "cyclical", 0), ("bull", "upside", 1)):
        scenario[name] = hkd(path("base", key)["endpoints"][ix]["value_per_share"])
    scenario.update(base_low=low, base_high=high, horizon_note="按同一股本、汇率和权益桥折现十五年分配及后续权益，弱情景采用保守端，上行采用兑现端。")
    assert scenario["structural_bear"] <= scenario["cyclical_bear"] <= low <= high <= scenario["bull"]
    growth = data["pbr_growth"]
    result = {
        "symbol": data["symbol"],
        "report_period": data["report_period"],
        "value_range": {"low": low, "high": high, "currency": "HKD"},
        "scenarios": scenario,
        "return_model": {
            "schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
            "model_as_of": data["cutoff"], "base_case_distributions_per_share": dividends,
            "base_case_terminal_equity_value_range_per_share": {
                "year_5": {name: hkd(e["year5_terminal_per_share"]) for name, e in zip(("low", "high"), ends)}
            }
        },
        "pbr_range_hkd": [hkd(book * (r - growth) / (e["cost"] - growth)) for r, e in zip(data["pbr_total_roe"], ends)],
        "payout_policy_sensitivity_hkd": {
            policy: [hkd(e["value_per_share"]) for e in path(policy)["endpoints"]]
            for policy in ("unchanged_35", "moderate_50")
        },
        "discount_rate_up_1pt_hkd": [hkd(e["value_per_share"]) for e in path("base", extra_cost=0.01)["endpoints"]],
        "tail_value_share": [round(e["year15_tail_share"], 4) for e in ends],
        "group_common_equity_rmb_million": facts["common_equity"],
        "stub_profit_rmb_million": round(facts["stub_common_profit"], 2),
        "initial_book_per_share_rmb": round(book, 4),
        "shares": round(shares * 1e6),
        "rmb_per_hkd": fx,
        "southbound_individual_dividend_tax": data["southbound_individual_dividend_tax"]
    }
    (here / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
