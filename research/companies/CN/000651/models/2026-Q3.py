"""格力普通股现金模型。金额亿元、股数亿股。标准库即可复算。"""

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def present_value(cashflows, rate, terminal=0.0):
    return sum(cash / (1 + rate) ** year for year, cash in enumerate(cashflows, 1)) + terminal / (
        1 + rate
    ) ** len(cashflows)


def opening(data):
    f = data["facts"]
    a = data["assumptions"]
    gross = (
        sum(
            f[key]
            for key in [
                "cash",
                "trading_assets",
                "current_noncurrent_assets",
                "other_debt_assets",
                "other_noncurrent_assets",
                "other_current_financial_products",
                "equity_and_loan_assets",
            ]
        )
        - f["nonfinancial_other_noncurrent"]
    )
    net_september = (
        gross
        - f["debt_and_lease"]
        - f["external_deposits"]
        - f["minority_equity"]
        - a["equity_and_loan_haircut"]
    )
    october_cash = f["buyback_paid_october_cumulative"] - f["buyback_paid_september"]
    future_buyback = f["minimum_buyback_budget"] - f["buyback_paid_october_cumulative"]
    total_bought_shares = (
        f["buyback_shares_october_cumulative"] + future_buyback / a["future_buyback_price"]
    )
    shares = f["issued_shares"] - total_bought_shares * a["cancellation_fraction"]
    # 残余净经营资产含递延税与应付返利。变动才进入经营现金。
    working_capital = (
        f["parent_equity"]
        - a["equity_and_loan_haircut"]
        - net_september
        - a["initial_operating_fixed_assets"]
    )
    return dict(
        gross_financial=gross,
        net_financial=net_september - october_cash,
        net_financial_september=net_september,
        october_cash=october_cash,
        future_buyback=future_buyback,
        shares=shares,
        working_capital=working_capital,
        equity=f["parent_equity"] - a["equity_and_loan_haircut"] - october_cash,
    )


def forecast(data):
    a, f = data["assumptions"], data["facts"]
    start = opening(data)
    funds, working, fixed = (
        start["net_financial"],
        start["working_capital"],
        a["initial_operating_fixed_assets"],
    )
    equity = start["equity"]
    parent_cash = a["parent_open_cash_budget"]
    parent_legal = f["parent_retained_earnings"]
    rows = []
    for i, revenue in enumerate(a["revenues"]):
        operating_profit = revenue * a["operating_net_margins"][i]
        finance_income = funds * a["financial_yield_after_tax"]
        profit = operating_profit + finance_income
        next_working = revenue * a["net_working_capital_ratio"]
        working_investment = next_working - working
        fixed_investment = a["capex"][i] - a["depreciation"][i]
        common_cash = profit - working_investment - fixed_investment
        buyback = start["future_buyback"] if i == 0 else 0.0
        intended_dividend = a["distributions_per_share"][i] * start["shares"]
        parent_profit = a["parent_share_of_profit"] * profit + a["annual_subsidiary_dividend"]
        award_expense = 15.0 if i == 0 else 0.0
        parent_legal += parent_profit - award_expense
        parent_cash_income = (
            a["parent_share_of_common_cash"] * common_cash + a["annual_subsidiary_dividend"]
        )
        parent_cash += parent_cash_income - buyback - a.get("parent_extra_payment", 0.0) * (i == 0)
        conversion_limit = a["parent_term_deposit_conversion_limit_year1"] if i == 0 else 0.0
        conversion = min(
            conversion_limit,
            max(0.0, a["parent_available_cash_floor"] + intended_dividend - parent_cash),
        )
        # 定存兑付为同一金融资产的流动性转换，集团资金不再增加。
        parent_cash += conversion
        dividend = min(
            intended_dividend,
            parent_legal,
            max(0.0, parent_cash - a["parent_available_cash_floor"]),
            max(0.0, funds + common_cash - buyback - a["net_financial_reserve"]),
        )
        parent_cash -= dividend
        parent_legal -= dividend
        funds += common_cash - dividend - buyback
        fixed += fixed_investment
        working = next_working
        equity += profit - dividend - buyback
        assert abs(equity - funds - fixed - working) < 1e-7
        assert parent_cash >= a["parent_available_cash_floor"] - 1e-7
        assert parent_legal >= -1e-7
        rows.append(
            dict(
                year=i + 1,
                revenue=revenue,
                operating_profit=operating_profit,
                finance_income=finance_income,
                common_profit_before_new_award=profit,
                common_reported_profit=profit - award_expense,
                new_award_expense=award_expense,
                common_cash=common_cash,
                working_investment=working_investment,
                fixed_investment=fixed_investment,
                dividend=dividend,
                distribution_per_share=dividend / start["shares"],
                buyback=buyback,
                net_financial=funds,
                reserve=a["net_financial_reserve"],
                excess_financial=funds - a["net_financial_reserve"],
                parent_cash=parent_cash,
                parent_deposit_conversion=conversion,
                parent_legal=parent_legal,
                equity=equity,
            )
        )
    return start, rows


def steady_policy_value(operating_profit, funds, reserve, yield_rate, rate, payout, surplus_rate):
    """稳定经营下的闭式分红现值，金融本金保留收益及真实分配权。

    C为超过必要储备的金融资产，A为经营利润加储备收益。
    C_next=(1+b)*C+c，D=p*A+(p*y+lambda)*C。
    b=(1-p)*y-lambda，c=(1-p)*A。
    对全部未来D求和，未将末期未分本金按面值重复加回。
    """
    excess = funds - reserve
    base_profit = operating_profit + reserve * yield_rate
    retention_growth = (1 - payout) * yield_rate - surplus_rate
    cash_loading = payout * yield_rate + surplus_rate
    retained_base_profit = (1 - payout) * base_profit
    assert rate > retention_growth
    value = payout * base_profit / rate + cash_loading * (excess + retained_base_profit / rate) / (
        rate - retention_growth
    )
    return value


def terminal_value(last, a, policy):
    """第五年末价值，第6—10年同经营轨迹按资本政策决定分配。

    之后经营零增长，分红比例与额外金融资金分配率保持政策端点。
    未分金融资产继续赚息，采用闭式现金流终值，不规定本金清空日。
    """
    rate = policy["cost_of_equity"]
    reserve = a["net_financial_reserve"]
    funds = last["net_financial"]
    operating_profit = last["operating_profit"]
    revenue = last["revenue"]
    working = revenue * a["net_working_capital_ratio"]
    legal = last.get("parent_legal", 1000000.0)
    cashflows = []
    years = []
    horizon = max(10, policy["policy_mature_year"]) - 5
    for offset in range(1, horizon + 1):
        year = 5 + offset
        growth = a["post_year5_growth"] if offset <= 5 else a["terminal_growth"]
        operating_profit *= 1 + growth
        next_revenue = revenue * (1 + growth)
        ratio = a["net_working_capital_ratio"] + 0.05 * min(offset, 5) / 5
        next_working = next_revenue * ratio
        reinvestment = next_working - working + (5.0 if revenue > 0 and offset <= 5 else 0.0)
        working = next_working
        profit = operating_profit + funds * a["financial_yield_after_tax"]
        common_cash = profit - reinvestment
        progress = min(1.0, max(0.0, (year - 6) / max(1, policy["policy_mature_year"] - 6)))
        payout = (
            policy["payout_start"] + (policy["payout_target"] - policy["payout_start"]) * progress
        )
        surplus_progress = min(
            1.0,
            max(
                0.0,
                (year - policy["surplus_start_year"] + 1)
                / max(1, policy["policy_mature_year"] - policy["surplus_start_year"] + 1),
            ),
        )
        surplus_rate = policy["surplus_distribution_rate"] * surplus_progress
        ordinary = payout * profit
        extra = surplus_rate * max(0.0, funds - reserve)
        legal += profit
        distribution = min(ordinary + extra, legal, max(0.0, funds + common_cash - reserve))
        legal -= distribution
        funds += common_cash - distribution
        assert legal >= -1e-7
        assert funds >= reserve - 1e-7
        cashflows.append(distribution)
        years.append(
            dict(
                year=year,
                operating_profit=operating_profit,
                revenue=next_revenue,
                reinvestment=reinvestment,
                profit=profit,
                ordinary_payout_ratio=payout,
                extra_cash_budget=extra,
                distribution=distribution,
                net_financial=funds,
                parent_legal=legal,
                common_cash=common_cash,
            )
        )
        revenue = next_revenue
    tail = steady_policy_value(
        operating_profit,
        funds,
        reserve,
        a["financial_yield_after_tax"],
        rate,
        policy["payout_target"],
        policy["surplus_distribution_rate"],
    )
    value = present_value(cashflows, rate, tail)
    return dict(
        value=value,
        first_future_distribution=cashflows[0],
        year10_distribution=years[4]["distribution"],
        year10_net_financial=years[4]["net_financial"],
        year10_parent_legal=years[4]["parent_legal"],
        future_years=years,
        policy_mature_year=policy["policy_mature_year"],
        terminal_tail_fraction=tail / (1 + rate) ** horizon / value,
    )


def calculate(data):
    a = data["assumptions"]
    start, rows = forecast(data)
    endpoints = {}
    for label in ["core_low", "core_high"]:
        policy = a[label]
        t = terminal_value(rows[-1], a, policy)
        terminal_per_share = t["value"] / start["shares"]
        dividends = [r["distribution_per_share"] for r in rows]
        current = present_value(dividends, policy["cost_of_equity"], terminal_per_share)
        endpoints[label] = dict(
            current_value=current,
            year5_value=terminal_per_share,
            terminal_fraction=terminal_per_share / (1 + policy["cost_of_equity"]) ** 5 / current,
            **t,
        )
    return dict(opening=start, years=rows, endpoints=endpoints)


def scenarios(data):
    output = {}
    configurations = {
        "cyclical_weak": {
            "revenues": [1450, 1500, 1600, 1698, 1732],
            "operating_net_margins": [0.09, 0.105, 0.115, 0.125, 0.125],
            "net_working_capital_ratio": -0.35,
            "distributions_per_share": [2.2, 2.3, 2.6, 3.05, 3.15],
        },
        "structural_damage": {
            "revenues": [1500, 1450, 1400, 1370, 1340],
            "operating_net_margins": [0.095, 0.09, 0.085, 0.08, 0.08],
            "net_working_capital_ratio": -0.29,
            "capex": [60] * 5,
            "distributions_per_share": [1.8, 1.7, 1.6, 1.5, 1.5],
            "post_year5_growth": -0.01,
            "post_year5_growth_years": 5,
        },
        "stronger_recovery": {
            "revenues": [1650, 1716, 1785, 1856, 1930],
            "operating_net_margins": [0.12, 0.125, 0.13, 0.13, 0.13],
            "capex": [65] * 5,
            "distributions_per_share": [3, 3.2, 3.4, 3.6, 3.8],
        },
        "margin_minus_one_point": {
            "operating_net_margins": [
                x - 0.01 for x in data["assumptions"]["operating_net_margins"]
            ]
        },
        "reserve_plus_200": {"net_financial_reserve": 1100},
        "parent_delayed_remittance": {"annual_subsidiary_dividend": 0, "parent_extra_payment": 120},
    }
    for name, updates in configurations.items():
        changed = deepcopy(data)
        changed["assumptions"].update(updates)
        result = calculate(changed)
        output[name] = {
            "current_low": result["endpoints"]["core_low"]["current_value"],
            "current_high": result["endpoints"]["core_high"]["current_value"],
            "distributions": [r["distribution_per_share"] for r in result["years"]],
            "year5_net_financial": result["years"][-1]["net_financial"],
            "minimum_parent_cash": min(r["parent_cash"] for r in result["years"]),
        }
    policy_comparisons = {
        "persistent_65_percent_payout": dict(
            payout_start=0.65, payout_target=0.65, surplus_distribution_rate=0
        ),
        "persistent_70_percent_payout": dict(
            payout_start=0.70, payout_target=0.70, surplus_distribution_rate=0
        ),
        "gradual_payout_without_extra_cash": dict(surplus_distribution_rate=0),
        "policy_improvement_delayed_five_years": dict(policy_mature_year=15, surplus_start_year=13),
        "strong_capital_return": dict(
            payout_start=0.70, payout_target=0.90, surplus_distribution_rate=0.03
        ),
    }
    for name, updates in policy_comparisons.items():
        changed = deepcopy(data)
        for label in ["core_low", "core_high"]:
            changed["assumptions"][label].update(updates)
        result = calculate(changed)
        output[name] = {
            label: result["endpoints"][label]["current_value"]
            for label in ["core_low", "core_high"]
        }
    return output


def auxiliary(data):
    """正常化经营盈利及资金的政策一致资本化，与五年显式预测作比较。"""
    a = data["assumptions"]
    start = opening(data)
    result = {}
    for label, profit in [("core_low", 195.84), ("core_high", 216.5)]:
        policy = a[label]
        value = steady_policy_value(
            profit,
            start["net_financial"],
            a["net_financial_reserve"],
            a["financial_yield_after_tax"],
            policy["cost_of_equity"],
            policy["payout_target"],
            policy["surplus_distribution_rate"],
        )
        normalization = (
            a["revenues"][0] * a["net_working_capital_ratio"] - start["working_capital"] + 5
        )
        result[label] = (value - normalization - start["future_buyback"]) / start["shares"]
    return result


def tests(data):
    # 送入正式现值链。10%下两期10及终值100恰好为100。
    assert abs(present_value([10, 10], 0.1, 100) - 100) < 1e-10
    # 正式终值链的无增长无额外本金特例，经营10+准备金收益2永续，价值120。
    a = deepcopy(data["assumptions"])
    a.update(
        net_financial_reserve=100,
        financial_yield_after_tax=0.02,
        post_year5_growth=0,
        terminal_growth=0,
        net_working_capital_ratio=-0.4,
    )
    policy = dict(
        cost_of_equity=0.1,
        payout_start=1.0,
        payout_target=1.0,
        surplus_distribution_rate=0.0,
        surplus_start_year=6,
        policy_mature_year=10,
    )
    t = terminal_value({"net_financial": 100, "operating_profit": 10, "revenue": 0}, a, policy)
    assert abs(t["value"] - 120) < 1e-9
    a.update(net_financial_reserve=0, financial_yield_after_tax=0)
    policy.update(
        payout_start=0.5, payout_target=0.5, surplus_distribution_rate=0.1, policy_mature_year=6
    )
    partial = terminal_value(
        {"net_financial": 100, "operating_profit": 10, "revenue": 0}, a, policy
    )
    # C_n=50+50*0.9^(n-1)，D_n=10+5*0.9^(n-1)，独立求和100+25。
    assert abs(partial["value"] - 125) < 1e-9
    result = calculate(data)
    alternate = deepcopy(data)
    for label in ["core_low", "core_high"]:
        alternate["assumptions"][label].update(
            payout_start=0.65, payout_target=0.65, surplus_distribution_rate=0
        )
    other = calculate(alternate)
    for label in ["core_low", "core_high"]:
        for base, alternative in zip(
            result["endpoints"][label]["future_years"],
            other["endpoints"][label]["future_years"],
            strict=True,
        ):
            for field in ["revenue", "operating_profit", "reinvestment"]:
                assert abs(base[field] - alternative[field]) < 1e-9
    for row in result["years"]:
        assert row["net_financial"] >= row["reserve"]
    assert len(result["years"]) == 5
    return [
        "present_value_hand_case",
        "terminal_value_hand_case",
        "partial_payout_geometric_hand_case",
        "same_operating_policy_comparison",
        "common_equity_bridge",
        "parent_cash_and_legal_limits",
        "five_year_contract",
    ]


def main():
    data = json.loads((ROOT / "2026-Q3-input.json").read_text())
    result = calculate(data)
    endpoints = result["endpoints"]
    value_range = {
        "low": round(endpoints["core_low"]["current_value"], 2),
        "high": round(endpoints["core_high"]["current_value"], 2),
        "currency": "CNY",
    }
    return_model = {
        "schema_version": 1,
        "method": "annual_common_equity_irr_v1",
        "currency": "CNY",
        "model_as_of": data["information_cutoff"],
        "base_case_distributions_per_share": [
            round(r["distribution_per_share"], 8) for r in result["years"]
        ],
        "base_case_terminal_equity_value_range_per_share": {
            "year_5": {
                "low": round(endpoints["core_low"]["year5_value"], 2),
                "high": round(endpoints["core_high"]["year5_value"], 2),
            }
        },
    }
    output = dict(
        symbol=data["symbol"],
        report_period=data["report_period"],
        value_range=value_range,
        return_model=return_model,
        return_model_note=data["return_model_note"],
        **result,
        auxiliary=auxiliary(data),
        scenarios=scenarios(data),
        tests=tests(data),
    )
    (ROOT / "2026-Q3-output.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "value_range": value_range,
                "return_model": return_model,
                "scenarios": output["scenarios"],
                "tests": output["tests"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
