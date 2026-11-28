"""python 2026-H1.py 读取同目录输入，重建每股税前价值与未来分红。"""
import json
from datetime import date
from math import isclose
from pathlib import Path

base = Path(__file__).resolve().parent
data = json.loads((base / "2026-H1-input.json").read_text())
facts = data["facts"]
shares = (facts["issued_shares"] - facts["treasury_shares"] + facts["dilution"]) / 1e6
investments = facts["jv"] + facts["associates"] + facts["other_investments"]
june_net_assets = facts["equity"] - investments
net_cash = facts["cash"] - facts["debt"]
other_net = june_net_assets - net_cash
assert june_net_assets + investments == facts["equity"]
recurring_cash = (facts["fy2025_ffo"] - facts["ukpn_whole_year_cash_to_all_owners"] * facts["ukpn_stake"]
                  + facts["ffo_adjustment"])
days = (date.fromisoformat(data["as_of"][:10]) - date.fromisoformat(facts["interim_end"])).days
stub_cash = days / 365 * (recurring_cash - data["base_bridge_capital"] + june_net_assets * data["base_bridge_deposit_rate"])
opening = june_net_assets + stub_cash - facts["june_interim_dividend_paid_september"]


def present_value(distributions, terminal, cost):
    periods = len(distributions)
    return sum(c / (1 + cost)**t for t, c in enumerate(distributions, 1)) + terminal / (1 + cost)**periods


def project(p):
    cash = opening - p["acquisition"]
    added_income = p["acquisition"] * p["acquisition_yield"]
    income = recurring_cash * p["cash_factor"] - p["net_topup"]
    for t, dps in enumerate(p["dps"]):
        period_income = income * (1 + p["cash_growth"])**t
        distributable = period_income + cash * p["cash_yield"] + added_income
        distribution = dps * shares
        closing_cash = cash + distributable - distribution
        assert closing_cash >= 0 and isclose(closing_cash + distribution, cash + distributable)
        cash = closing_cash

    cost, g = p["r"], p["term_growth"]
    assert cost > g
    operating_value = period_income * (1 + g) / (cost - g)
    terminal = (operating_value + cash + added_income / cost) / shares
    pv = present_value(p["dps"], terminal, cost)
    return dict(value=round(pv, 2), terminal=round(terminal, 2), year5_net_cash=round(cash),
                terminal_pv_fraction=round(terminal / (1 + cost)**5 / pv, 3))


assert isclose(present_value([1, 1], 10, 0.10), 10)
paths = {name: project(params) for name, params in data["scenarios"].items()}
values = {name: row["value"] for name, row in paths.items()}
assert list(values.values()) == sorted(values.values())
low, high = paths["base_low"], paths["base_high"]
base_low = data["scenarios"]["base_low"]
out = {
    "symbol": data["symbol"], "report_period": data["period"],
    "value_range": {"low": low["value"], "high": high["value"], "currency": "HKD"},
    "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
                     "model_as_of": data["as_of"], "base_case_distributions_per_share": base_low["dps"],
                     "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low["terminal"], "high": high["terminal"]}}},
    "paths": paths, "equity_bridge_hkd_m": {"june_net_cash": net_cash, "other_net": other_net, "stub_cash_est": round(stub_cash),
                                            "opening_nonoperating_net_assets_est": round(opening), "annual_recurring_cash_est": recurring_cash},
    "adjusted_book_value_per_share": [round((opening + multiple * investments) / shares, 2) for multiple in data["book_multiples"]],
    "sensitivities_base_low": {"cash_yield_minus_100bp": project({**base_low, "cash_yield": base_low["cash_yield"] - 0.01})["value"],
                              "recurring_cash_minus_10pct": project({**base_low, "cash_factor": 0.9})["value"]}
}
(base / "2026-H1-output.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
