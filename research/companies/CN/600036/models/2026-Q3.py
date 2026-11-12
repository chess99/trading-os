"""招商银行年度普通股模型。金额为人民币百万元，股数为百万股。

Run `python 2026-Q3.py`; no third-party dependency is required.
K is the business capital budget, X is additional low-yield retained capital.
Both belong to common shareholders. Neither is added again to the valuation.
Cash dividends use the preceding earnings cohort, consistent with the next
January/July payment convention. The perpetual tail has an exact closed form.
"""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = json.loads((ROOT / "2026-Q3-input.json").read_text())


def tail_value(capital, extra, previous_profit, rate, growth, payout, yield_extra, cost):
    """Solve V=a*K+b*X+c*P for the same cash/retention transition as step()."""
    denominator = (cost - yield_extra) * (1 + cost) + payout * yield_extra
    b = payout * yield_extra / denominator
    c = payout * (1 - b) / (1 + cost)
    a = (b * (rate - growth) + c * rate) / (cost - growth)
    return a * capital + b * extra + c * previous_profit, (a, b, c)


def step(capital, extra, previous_profit, rate, growth, payout, yield_extra):
    profit = capital * rate + extra * yield_extra
    distribution = previous_profit * payout
    next_capital = capital * (1 + growth)
    next_extra = extra + profit - distribution - capital * growth
    assert math.isclose(
        next_capital + next_extra, capital + extra + profit - distribution, abs_tol=1e-7
    )
    return next_capital, next_extra, profit, distribution


def simulate(policy, scenario="base", rate_tail_shift=0.0):
    fact = INPUT["facts"]
    setting = INPUT["scenarios"][scenario]
    capital = fact["common_equity"] + fact["stub_common_profit"]
    initial = capital
    extra = 0.0
    previous_profit = fact["forecast_2026_common_profit"]
    parent_equity = (
        fact["parent_common_equity"]
        + fact["stub_common_profit"] * setting["parent_profit_share"][0]
    )
    retained_profit = (
        fact["parent_undistributed_profit"]
        + fact["stub_common_profit"] * setting["parent_profit_share"][0]
    )
    reserve = fact["parent_general_reserve"]
    group_gap = fact["common_equity"] - fact["group_cet1"]
    parent_gap = fact["parent_common_equity"] - fact["parent_cet1"]
    group_rwa = fact["group_cet1"] / fact["group_cet1_ratio"]
    parent_rwa = fact["parent_cet1"] / fact["parent_cet1_ratio"]
    group_weighted_rwa = fact["group_cet1"] / fact["group_weighted_cet1_ratio"]
    parent_weighted_rwa = fact["parent_cet1"] / fact["parent_weighted_cet1_ratio"]
    group_leverage_assets = fact["group_leverage_exposure"]
    # Parent exposure is the Q3 group denominator scaled by parent/group assets.
    # It remains a labelled proxy because Q3 does not disclose its own denominator.
    parent_leverage_assets = fact["parent_leverage_exposure_proxy"]
    group_hqla = fact["group_hqla_q3"]
    parent_cash = fact["parent_cash_equivalents"]
    group_net_outflow = fact["group_net_outflow_q3"]
    group_at1 = fact["at1_capital"]
    parent_at1 = fact["parent_at1_capital"]
    group_tier2 = fact["group_tier2"]
    parent_tier2 = fact["parent_tier2"]
    group_weighted_tier2 = fact["group_weighted_tier2"]
    parent_weighted_tier2 = fact["parent_weighted_tier2"]
    at1_coupon = fact["at1_coupon_budget"]
    rows = []
    for index, proposed_payout in enumerate(INPUT["policies"][policy]):
        proposed_payout = min(proposed_payout, setting["payout_cap"])
        rate = setting["rates"][index] + rate_tail_shift * max(0.0, (index - 4) / 10)
        growth = setting["growth"][index]
        previous_equity = capital + extra
        next_capital, next_extra, profit, desired_dividend = step(
            capital, extra, previous_profit, rate, growth, proposed_payout, INPUT["extra_yield"]
        )
        parent_profit = profit * setting["parent_profit_share"][index]
        at1_coupon *= 1 + growth
        statutory_reserve = max(0.0, parent_profit + at1_coupon) * 0.10
        general_reserve_addition = reserve * max(growth, 0.0)
        available_legal_profit = (
            retained_profit + parent_profit - statutory_reserve - general_reserve_addition
        )
        # Growth in risk budgets includes structural capital-density changes.
        risk_growth = growth + setting["risk_density_growth"][index]
        group_rwa *= 1 + risk_growth
        parent_rwa *= 1 + risk_growth
        group_weighted_rwa *= 1 + risk_growth
        parent_weighted_rwa *= 1 + risk_growth
        group_gap *= 1 + growth
        parent_gap *= 1 + growth
        group_leverage_assets *= 1 + growth
        parent_leverage_assets *= 1 + growth
        group_hqla *= 1 + growth
        group_net_outflow *= 1 + growth
        parent_cash *= 1 + growth
        group_before = previous_equity + profit
        parent_before = parent_equity + parent_profit
        # Net common ROE includes the funding cost of maintaining the AT1/T2
        # capital mix. New non-common instruments do not create common equity.
        group_at1 *= 1 + growth
        parent_at1 *= 1 + growth
        group_tier2 *= 1 + growth
        parent_tier2 *= 1 + growth
        group_weighted_tier2 *= 1 + growth
        parent_weighted_tier2 *= 1 + growth
        cap_limits = [
            group_before - group_gap - 0.12 * group_rwa,
            parent_before - parent_gap - 0.12 * parent_rwa,
            group_before - group_gap - 0.10 * group_weighted_rwa,
            parent_before - parent_gap - 0.10 * parent_weighted_rwa,
            group_before - group_gap + group_at1 - 0.13 * group_rwa,
            parent_before - parent_gap + parent_at1 - 0.13 * parent_rwa,
            group_before - group_gap + group_at1 + group_tier2 - 0.15 * group_rwa,
            parent_before - parent_gap + parent_at1 + parent_tier2 - 0.15 * parent_rwa,
            group_before - group_gap + group_at1 - 0.11 * group_weighted_rwa,
            parent_before - parent_gap + parent_at1 - 0.11 * parent_weighted_rwa,
            group_before - group_gap + group_at1 + group_weighted_tier2 - 0.13 * group_weighted_rwa,
            parent_before
            - parent_gap
            + parent_at1
            + parent_weighted_tier2
            - 0.13 * parent_weighted_rwa,
            group_before - group_gap + group_at1 - 0.05 * group_leverage_assets,
            parent_before - parent_gap + parent_at1 - 0.05 * parent_leverage_assets,
        ]
        liquidity_capacity = max(0.0, min(group_hqla - 1.4 * group_net_outflow, 0.5 * parent_cash))
        dividend = max(
            0.0, min(desired_dividend, available_legal_profit, liquidity_capacity, *cap_limits)
        )
        next_extra += desired_dividend - dividend
        equity = next_capital + next_extra
        parent_equity = parent_before - dividend
        retained_profit = available_legal_profit - dividend
        reserve += general_reserve_addition
        assert next_extra >= -1e-6, "Business capital requires outside common financing"
        assert retained_profit >= -1e-6
        assert math.isclose(equity, previous_equity + profit - dividend, abs_tol=1e-7)
        rows.append(
            {
                "year": index + 1,
                "common_profit": profit,
                "dividend": dividend,
                "business_capital": next_capital,
                "extra_retained_capital": next_extra,
                "common_equity": equity,
                "parent_common_equity": parent_equity,
                "parent_undistributed_profit": retained_profit,
                "group_cet1_ratio": (equity - group_gap) / group_rwa,
                "parent_cet1_ratio": (parent_equity - parent_gap) / parent_rwa,
                "parent_weighted_cet1_ratio": (parent_equity - parent_gap) / parent_weighted_rwa,
                "group_lcr_after_dividend": (group_hqla - dividend) / group_net_outflow,
                "parent_cash_after_dividend": parent_cash - dividend,
                "legal_surplus": retained_profit,
                "dividend_reduction": desired_dividend - dividend,
                "cash_capacity": liquidity_capacity,
            }
        )
        capital, extra, previous_profit = next_capital, next_extra, profit
    return initial, rows


def value_path(policy, scenario="base", extra_cost=0.0, terminal_rate_shift=0.0):
    fact = INPUT["facts"]
    initial, baseline_rows = simulate(policy, scenario)
    setting = INPUT["scenarios"][scenario]
    endpoints = []
    for endpoint in INPUT["endpoints"]:
        initial, rows = simulate(policy, scenario, endpoint["terminal_rate"] - 0.105)
        cost = endpoint["cost"] + extra_cost
        terminal_rate = (
            endpoint["terminal_rate"] + setting["terminal_rate_shift"] + terminal_rate_shift
        )
        tail, coefficients = tail_value(
            rows[-1]["business_capital"],
            rows[-1]["extra_retained_capital"],
            rows[-1]["common_profit"],
            terminal_rate,
            setting["terminal_growth"],
            min(INPUT["policies"][policy][-1], setting["payout_cap"]),
            INPUT["extra_yield"],
            cost,
        )
        pv_dividends = sum(row["dividend"] / (1 + cost) ** row["year"] for row in rows)
        pv_tail = tail / (1 + cost) ** len(rows)
        value = pv_dividends + pv_tail
        fifth_year_value = sum(
            row["dividend"] / (1 + cost) ** (row["year"] - 5) for row in rows[5:]
        ) + tail / (1 + cost) ** (len(rows) - 5)
        # Independent clean-surplus residual-income identity on this finite path.
        previous_equity = initial
        residual_income_pv = 0.0
        for row in rows:
            residual_income_pv += (row["common_profit"] - cost * previous_equity) / (
                1 + cost
            ) ** row["year"]
            previous_equity = row["common_equity"]
        residual_value = (
            initial + residual_income_pv + (tail - previous_equity) / (1 + cost) ** len(rows)
        )
        assert math.isclose(value, residual_value, abs_tol=1e-7)
        endpoints.append(
            {
                "value_per_share": value / fact["shares_million"],
                "year5_terminal_per_share": fifth_year_value / fact["shares_million"],
                "year15_tail_share": pv_tail / value,
                "cost": cost,
                "terminal_business_roe": terminal_rate,
                "tail_coefficients": coefficients,
                "year15_common_profit": rows[-1]["common_profit"],
                "year15_extra_capital": rows[-1]["extra_retained_capital"],
                "min_parent_cet1": min(row["parent_cet1_ratio"] for row in rows),
                "dividend_reductions": sum(row["dividend_reduction"] for row in rows),
            }
        )
    return {"endpoints": endpoints, "rows": baseline_rows}


def self_test():
    # A no-growth company earning 10 on 100 and distributing all prior earnings
    # is worth 100 at a 10% discount rate, through the production tail function.
    v, _ = tail_value(100, 0, 10, 0.1, 0, 1, 0, 0.1)
    assert math.isclose(v, 100, abs_tol=1e-9)
    # A 5%-growth company with the fiscal-payment lag pays 5 now from 9.5238
    # prior earnings. Gordon independently gives 5/(10%-5%)=100.
    v, _ = tail_value(100, 0, 10 / 1.05, 0.1, 0.05, 0.525, 0, 0.1)
    assert math.isclose(v, 100, abs_tol=1e-9)
    k, x, p, d = step(100, 0, 10 / 1.05, 0.1, 0.05, 0.525, 0)
    assert math.isclose(k, 105) and math.isclose(x, 0, abs_tol=1e-9)
    assert math.isclose(d, 5)
    # Closed form must obey a one-year Bellman equality for a nontrivial state.
    state = (100, 20, 12)
    v, _ = tail_value(*state, 0.11, 0.03, 0.7, 0.015, 0.1)
    k, x, p, d = step(*state, 0.11, 0.03, 0.7, 0.015)
    continuation, _ = tail_value(k, x, p, 0.11, 0.03, 0.7, 0.015, 0.1)
    assert math.isclose(v, (d + continuation) / 1.1, abs_tol=1e-9)


if __name__ == "__main__":
    self_test()
    output = {
        "symbol": "CN:600036",
        "report_period": "2026-Q3",
        "return_model_note": INPUT["return_model_note"],
    }
    paths = {name: value_path(name) for name in INPUT["policies"]}
    paths.update({name: value_path("base", name) for name in ["cyclical", "structural", "upside"]})
    base = paths["base"]
    output["value_range"] = {
        "low": round(base["endpoints"][0]["value_per_share"], 2),
        "high": round(base["endpoints"][1]["value_per_share"], 2),
        "currency": "CNY",
    }
    output["return_model"] = {
        "schema_version": 1,
        "method": "annual_common_equity_irr_v1",
        "currency": "CNY",
        "model_as_of": INPUT["information_cutoff"],
        "base_case_distributions_per_share": [
            round(row["dividend"] / INPUT["facts"]["shares_million"], 4) for row in base["rows"][:5]
        ],
        "base_case_terminal_equity_value_range_per_share": {
            "year_5": {
                "low": round(base["endpoints"][0]["year5_terminal_per_share"], 2),
                "high": round(base["endpoints"][1]["year5_terminal_per_share"], 2),
            }
        },
    }
    output["paths"] = paths
    output["sensitivity_cost_plus_1pt"] = value_path("base", extra_cost=0.01)["endpoints"]
    output["sensitivity_terminal_roe_minus_1pt"] = value_path("base", terminal_rate_shift=-0.01)[
        "endpoints"
    ]
    output["self_tests"] = "4 production-function hand cases and clean-surplus identities passed"
    (ROOT / "2026-Q3-output.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {key: output[key] for key in ["value_range", "return_model", "self_tests"]},
            ensure_ascii=False,
            indent=2,
        )
    )
