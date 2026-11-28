"""福耀 H 股普通股权益，复用发行人经营、资本与母公司分配模型。"""
import hashlib
import json
import math
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent


def per_h_share(cny_per_ordinary, ratio, cny_per_hkd):
    return cny_per_ordinary * ratio / cny_per_hkd


def cycle_with_completion_spending(issuer, model, first_year_capex):
    """排产下调但已定工程仍付款。经营终态相同，重算前五年的钱、债和分红。"""
    original = model["rows"]
    old_parent = parent = issuer["PARENT0"]
    old_legal = legal = issuer["LEGAL0"] - model["opening_policy_appropriation"]
    old_cash = cash = issuer["CASH0"]
    old_debt = debt = issuer["DEBT0"]
    rows = []
    for old in original:
        extra_spending = first_year_capex - old["capex"] if old["year"] == 1 else 0
        interest_change = ((cash - old_cash) * 0.02 - (debt - old_debt) * 0.03) * 0.8
        free = old["free_equity_cash"] - extra_spending + interest_change
        # 同一收入和上划路径；此处只增加子公司已定工程现金支出。
        available_parent = parent + old["parent_cash"] - old_parent + old["dividend"] - old["new_borrowing"]
        distributable = legal + old["parent_legal_profit"] - old_legal + old["dividend"]
        floor = old["minimum_cash"]
        dividend = max(0, min(0.6 * (old["net_profit"] + interest_change), free,
                              cash + free - floor, available_parent - 3, distributable))
        credit = 2 - (debt - issuer["DEBT0"])
        group_funding = issuer["finance_step"](cash, free, dividend, floor, credit)
        parent_funding = issuer["finance_step"](available_parent, 0, dividend, 3, credit)
        assert group_funding is not None and parent_funding is not None
        draw = max(group_funding[1], parent_funding[1])
        cash += free - dividend + draw
        debt += draw
        parent = available_parent - dividend + draw
        legal = distributable - dividend
        assert cash >= parent - 1e-9
        rows.append({**old, "cash": cash, "debt": debt, "parent_cash": parent, "parent_legal_profit": legal,
                     "new_borrowing": draw, "dividend": dividend, "dps": dividend / issuer["SHARES"],
                     "free_equity_cash": free, "capex": old["capex"] + extra_spending})
        old_cash, old_debt = old["cash"], old["debt"]
        old_parent, old_legal = old["parent_cash"], old["parent_legal_profit"]

    r = model["rate"]
    excess = max(0, cash - rows[-1]["minimum_cash"])
    parent_excess = min(excess, max(0, parent - 3))
    repaid = min(parent_excess, debt, issuer["PARENT_EXTERNAL_DEBT"])
    immediate = min(parent_excess - repaid, max(0, legal))
    deferred = excess - repaid - immediate
    bridge = immediate + issuer["realize_principal"](deferred, 1, 3, 0.03, r) - (debt - repaid)
    terminal = (model["enterprise_value_year5"] + bridge) / issuer["SHARES"]
    pv = issuer["pv"]([row["dps"] for row in rows], r, terminal)
    return {**model, "rows": rows, "terminal_per_share": terminal, "current_value": pv,
            "financial_value_year5": bridge, "terminal_pv_fraction": terminal / (1 + r) ** 5 / pv}


def calculate(facts):
    relative = facts["issuer_engine"]
    source = next(parent / relative for parent in HERE.parents if (parent / relative).is_file())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == facts["issuer_engine_sha256"]
    issuer = runpy.run_path(str(source))
    issuer["tests"]()
    shares = facts["shares"]
    participating = shares["a"] + shares["h"] - shares["treasury"]
    assert round(issuer["SHARES"] * 1e9) == participating
    available_cash = facts["sep_cash_equivalents_cny"] + facts["sep_trading_assets_cny"] - facts["sep_dividends_payable_cny"]
    assert round(issuer["CASH0"] * 1e9) == available_cash
    assert facts["interim_dividend"]["payment_date"] < facts["information_cutoff"][:10]

    def hkd(cny, digits=2):
        return round(per_h_share(cny, shares["ordinary_per_h"], facts["cny_per_hkd"]), digits)

    assert per_h_share(8, 1, 0.8) == 10
    paths = {}
    for key, assumptions in facts["paths"].items():
        model = issuer["run"](**assumptions)
        if key == "cyclical_bear":
            unchanged = cycle_with_completion_spending(issuer, model, model["rows"][0]["capex"])
            assert math.isclose(unchanged["current_value"], model["current_value"], abs_tol=1e-10)
            model = cycle_with_completion_spending(issuer, model, facts["cycle_first_year_capex_bn_cny"])
        assert model["shares"] == issuer["SHARES"]
        rows = model["rows"]
        distributions = [row["dps"] for row in rows]
        pv = issuer["pv"](distributions, model["rate"], model["terminal_per_share"])
        assert math.isclose(pv, model["current_value"], rel_tol=1e-12)
        cash = issuer["CASH0"]
        for row in rows:
            assert math.isclose(cash + row["free_equity_cash"] - row["dividend"] + row["new_borrowing"], row["cash"])
            assert min(row["cash"] - row["minimum_cash"], row["parent_cash"] - 3, row["parent_legal_profit"]) >= -1e-8
            cash = row["cash"]
        paths[key] = {
            "present_value_hkd": hkd(pv), "terminal_year5_hkd": hkd(model["terminal_per_share"]),
            "terminal_pv_share": round(model["terminal_pv_fraction"], 4),
            "cash_distributions_hkd": [hkd(d, 4) for d in distributions],
            "first_year_nopat_bn_cny": round(rows[0]["nopat"], 4),
            "year5_financial_bridge_bn_cny": round(model["financial_value_year5"], 4)
        }

    names = ["structural_bear", "cyclical_bear", "base_low", "base_high", "bull"]
    values = {name: paths[name]["present_value_hkd"] for name in names}
    assert list(values.values()) == sorted(values.values())
    value_range = {"low": values["base_low"], "high": values["base_high"], "currency": "HKD"}
    holder = {
        "schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
        "model_as_of": facts["information_cutoff"],
        "base_case_distributions_per_share": paths["base_mid"]["cash_distributions_hkd"],
        "base_case_terminal_equity_value_range_per_share": {"year_5": {
            "low": paths["base_low"]["terminal_year5_hkd"], "high": paths["base_high"]["terminal_year5_hkd"]}}
    }
    normalized_model = issuer["run"]()
    initial_min_cash = 0.08 * 46.5
    equity_bridge = issuer["CASH0"] - issuer["DEBT0"] - initial_min_cash
    normalized_profit = normalized_model["rows"][0]["nopat"]
    secondary = [hkd((normalized_profit * multiple + equity_bridge) / issuer["SHARES"])
                 for multiple in facts["secondary_ev_nopat_multiples"]]
    return {
        "symbol": facts["symbol"], "report_period": facts["report_period"],
        "information_cutoff": facts["information_cutoff"], "value_range": value_range, "return_model": holder,
        "scenarios": {"currency": "HKD", **values, "horizon_note": "各情景为截止时点每股 H 股港元价值，已除息款归原登记股东。"},
        "secondary_value_hkd": secondary, "cash_after_payable_cny": available_cash,
        "participating_shares": participating, "paths": paths
    }


if __name__ == "__main__":
    facts = json.loads((HERE / "2026-Q3-input.json").read_text())
    result = calculate(facts)
    (HERE / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
