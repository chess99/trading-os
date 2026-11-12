"""腾讯普通股估值，标准库即可复算。金额十亿元人民币，输出每股港元。
运行 python 2026-H1.py，输入与输出与脚本同目录。
股份薪酬保留在费用，等额现金用于抵消未来奖励稀释，股数保持不变。
"""

import copy
import json
import math
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent


def operating_cashflows(inputs):
    plan = inputs["first_five_years"]
    rows = []
    for year in range(5):
        revenue = sum(
            plan[key][year]
            for key in [
                "vas_revenue",
                "advertising_revenue",
                "fintech_business_revenue",
                "other_revenue",
            ]
        )
        gross_profit = (
            sum(
                plan[segment + "_revenue"][year] * plan[segment + "_gross_margin"][year]
                for segment in ["vas", "advertising", "fintech_business"]
            )
            + plan["other_gross_profit"][year]
        )
        operating_profit = gross_profit - plan["operating_expenses_including_sbc"][year]
        common_operating_profit = (
            operating_profit * (1 - inputs["tax_rate"]) - plan["minority_cash_entitlement"][year]
        )
        owner_cashflow = (
            common_operating_profit
            + plan["depreciation_amortization"][year]
            - sum(
                plan[key][year]
                for key in [
                    "cash_capex_excluding_content",
                    "cash_content",
                    "lease_principal",
                    "working_capital_and_compute_prepayment_increase",
                    "cash_interest_net_of_base_treasury_income",
                ]
            )
        )
        rows.append(
            {
                "year": year + 1,
                "revenue": revenue,
                "operating_profit": operating_profit,
                "common_operating_profit_after_tax": common_operating_profit,
                "owner_cashflow": owner_cashflow,
            }
        )
    return rows


def continuing_operations_value(last_cashflow, growth_rates, terminal_growth, cost_equity):
    """计算估值时点之后五年过渡现金和永续现金的经济价值。"""
    cashflow = last_cashflow
    present_value = 0
    for year, growth in enumerate(growth_rates, start=1):
        cashflow *= 1 + growth
        present_value += cashflow / (1 + cost_equity) ** year
    terminal_value = cashflow * (1 + terminal_growth) / (cost_equity - terminal_growth)
    return present_value + terminal_value / (1 + cost_equity) ** len(growth_rates)


def holder_value(
    cashflows,
    dividends,
    start_cash,
    portfolio,
    portfolio_income,
    new_investment,
    cash_yield,
    operating_buffer,
    terminal_operations,
    rate,
):
    """明确已分配现金、投资出资和第五年现金，避免重复加回。"""
    cash = start_cash
    dividend_pv = 0
    rows = []
    for year, (cashflow, dividend) in enumerate(zip(cashflows, dividends, strict=True), start=1):
        opening_cash = cash
        interest = max(opening_cash, 0) * cash_yield
        investment = new_investment if year == 1 else 0
        cash += cashflow + portfolio_income + interest - dividend - investment
        portfolio += investment
        assert math.isclose(
            cash - opening_cash,
            cashflow + portfolio_income + interest - dividend - investment,
            abs_tol=1e-8,
        )
        rows.append(
            {
                "year": year,
                "opening_common_net_cash": opening_cash,
                "owner_cashflow": cashflow,
                "portfolio_income": portfolio_income,
                "cash_interest": interest,
                "common_dividend": dividend,
                "investment_paid": investment,
                "closing_common_net_cash": cash,
            }
        )
        dividend_pv += dividend / (1 + rate) ** year
    terminal = terminal_operations + cash - operating_buffer + portfolio
    value = dividend_pv + terminal / (1 + rate) ** len(cashflows)
    return {
        "equity_value": value,
        "terminal_equity_value": terminal,
        "terminal_operating_value": terminal_operations,
        "terminal_common_net_cash": cash,
        "terminal_portfolio_value": portfolio,
        "dividend_pv": dividend_pv,
        "terminal_pv_fraction": (value - dividend_pv) / value,
        "cash_bridge": rows,
    }


def parent_capacity(inputs, dividend_plan):
    plan = inputs["first_five_years"]
    cash = inputs["parent_initial_liquidity"]
    reserve = inputs["parent_initial_distributable_reserve"]
    rows = []
    for year, dividend in enumerate(dividend_plan):
        receipt = plan["parent_receipt_budget"][year]
        profit = plan["parent_statutory_profit_budget"][year]
        interest = plan["parent_interest_cash"][year]
        repurchase = plan["parent_sbc_offset_repurchases"][year]
        cash += receipt - dividend - interest - repurchase
        reserve += profit - dividend - repurchase
        if cash < 0 or reserve < 0:
            raise ValueError("付款母公司资金或储备不足，须调整分配路径")
        rows.append(
            {
                "year": year + 1,
                "cash_receipt_budget": receipt,
                "statutory_profit_budget": profit,
                "dividend": dividend,
                "interest": interest,
                "sbc_offset_repurchases": repurchase,
                "ending_liquidity": cash,
                "ending_distributable_reserve": reserve,
            }
        )
    return rows


def scenario(inputs, parameters):
    operating = operating_cashflows(inputs)
    cashflows = [row["owner_cashflow"] for row in operating]
    terminal_operations = continuing_operations_value(
        cashflows[-1],
        inputs["tail_fcf_growth_years_6_to_10"],
        parameters["terminal_growth"],
        parameters["cost_equity"],
    )
    portfolio = (
        inputs["portfolio_listed"] * parameters["listed_recovery"]
        + inputs["portfolio_unlisted"] * parameters["unlisted_recovery"]
    )
    valuation = holder_value(
        cashflows,
        inputs["first_five_years"]["common_dividends"],
        inputs["common_net_cash"],
        portfolio,
        inputs["portfolio_dividends"],
        inputs["new_investment_commitment"],
        inputs["cash_interest_rate"],
        inputs["operating_cash_buffer"],
        terminal_operations,
        parameters["cost_equity"],
    )
    multiplier = inputs["hkd_per_cny"] / inputs["diluted_shares"]
    valuation.update(
        {
            "value_per_share": valuation["equity_value"] * multiplier,
            "terminal_per_share": valuation["terminal_equity_value"] * multiplier,
            "operating_projection": operating,
            "parent_capacity": parent_capacity(
                inputs, inputs["first_five_years"]["common_dividends"]
            ),
        }
    )
    return valuation


def verify():
    # 将常数现金流特例送入正式估值链，应与100/10%=1000一致。
    operating_value = continuing_operations_value(100, [0] * 5, 0, 0.1)
    result = holder_value([100] * 5, [100] * 5, 0, 0, 0, 0, 0, 0, operating_value, 0.1)
    assert math.isclose(result["equity_value"], 1000, abs_tol=1e-8)
    # 现金以资本成本再投资时，延迟分配不改变价值。
    retained = holder_value([100] * 5, [0] * 5, 0, 0, 0, 0, 0.1, 0, operating_value, 0.1)
    assert math.isclose(retained["equity_value"], 1000, abs_tol=1e-8)
    assert math.isclose(result["terminal_common_net_cash"], 0, abs_tol=1e-8)


def main():
    inputs = json.loads((DIRECTORY / "2026-H1-inputs.json").read_text())
    verify()
    results = {
        name: scenario(inputs, inputs[name]) for name in ["core_low", "core_high", "reference"]
    }
    cyclical = copy.deepcopy(inputs)
    for key in ["vas_revenue", "advertising_revenue", "fintech_business_revenue"]:
        cyclical["first_five_years"][key] = [
            value * factor
            for value, factor in zip(
                inputs["first_five_years"][key], [0.92, 0.96, 1, 1, 1], strict=True
            )
        ]
    cyclical["first_five_years"]["common_dividends"] = [42, 47, 58, 65, 72]
    cyclical["first_five_years"]["parent_receipt_budget"] = [85, 95, 110, 120, 130]
    cyclical["first_five_years"]["parent_statutory_profit_budget"] = [65, 80, 110, 120, 130]
    results["cyclical_weak"] = scenario(cyclical, inputs["reference"])
    structural = copy.deepcopy(inputs)
    structural["first_five_years"]["vas_revenue"] = [405, 412, 420, 428, 436]
    structural["first_five_years"]["advertising_revenue"] = [185, 194, 204, 214, 225]
    structural["first_five_years"]["fintech_business_revenue"] = [250, 263, 276, 290, 304]
    structural["first_five_years"]["advertising_gross_margin"] = [0.53] * 5
    structural["first_five_years"]["fintech_business_gross_margin"] = [0.47] * 5
    structural["first_five_years"]["operating_expenses_including_sbc"] = [225, 235, 245, 255, 265]
    structural["first_five_years"]["cash_capex_excluding_content"] = [200, 180, 155, 145, 145]
    structural["first_five_years"]["depreciation_amortization"] = [95, 112, 120, 125, 130]
    structural["first_five_years"]["working_capital_and_compute_prepayment_increase"] = [
        35,
        20,
        12,
        10,
        10,
    ]
    structural["first_five_years"]["common_dividends"] = [30, 30, 35, 40, 45]
    structural["first_five_years"]["parent_receipt_budget"] = [80, 85, 90, 100, 110]
    structural["first_five_years"]["parent_statutory_profit_budget"] = [45, 55, 65, 75, 85]
    structural["tail_fcf_growth_years_6_to_10"] = [0.025] * 5
    structural["common_net_cash"] -= 15
    structural_parameters = dict(inputs["core_low"], terminal_growth=0.01, cost_equity=0.115)
    results["structural_adverse"] = scenario(structural, structural_parameters)
    optimistic = copy.deepcopy(inputs)
    for key in ["vas_revenue", "advertising_revenue", "fintech_business_revenue"]:
        optimistic["first_five_years"][key] = [
            value * factor
            for value, factor in zip(
                inputs["first_five_years"][key], [1.02, 1.04, 1.06, 1.08, 1.10], strict=True
            )
        ]
    optimistic["first_five_years"]["cash_capex_excluding_content"] = [190, 195, 200, 205, 210]
    optimistic["first_five_years"]["operating_expenses_including_sbc"] = [230, 250, 272, 292, 315]
    results["optimistic"] = scenario(optimistic, inputs["core_high"])
    capital_stress = copy.deepcopy(inputs)
    capital_stress["first_five_years"]["cash_capex_excluding_content"] = [
        value + 30 for value in inputs["first_five_years"]["cash_capex_excluding_content"]
    ]
    results["persistent_extra_30bn_capex"] = scenario(capital_stress, inputs["reference"])
    rate_stress = dict(inputs["reference"], cost_equity=0.11)
    results["cost_equity_plus_1pp"] = scenario(inputs, rate_stress)
    parent_delay = copy.deepcopy(inputs)
    parent_delay["first_five_years"]["parent_receipt_budget"][0] -= 40
    parent_delay["first_five_years"]["parent_receipt_budget"][1] += 40
    parent_delay["first_five_years"]["common_dividends"] = [10, 89, 58, 65, 72]
    results["parent_receipt_delay_40bn"] = scenario(parent_delay, inputs["reference"])
    faster_distribution = copy.deepcopy(inputs)
    owner_cash = [row["owner_cashflow"] for row in operating_cashflows(inputs)]
    faster_distribution["first_five_years"]["common_dividends"] = [47] + [
        value * 0.8 for value in owner_cash[1:]
    ]
    faster_distribution["first_five_years"]["parent_receipt_budget"] = [90] + [
        value * 0.8 + repurchase + 16
        for value, repurchase in zip(
            owner_cash[1:],
            inputs["first_five_years"]["parent_sbc_offset_repurchases"][1:],
            strict=True,
        )
    ]
    faster_distribution["first_five_years"]["parent_statutory_profit_budget"] = [
        value + 10 for value in faster_distribution["first_five_years"]["parent_receipt_budget"]
    ]
    results["higher_cash_distribution_same_business"] = scenario(
        faster_distribution, inputs["reference"]
    )
    auxiliary = inputs["auxiliary"]
    normalized_earnings = (
        auxiliary["normalized_operating_profit"] * (1 - inputs["tax_rate"])
        - auxiliary["minority_profit"]
        - auxiliary["maintenance_cash_including_content_and_leases"]
        + auxiliary["depreciation_amortization"]
    )
    result = {
        "symbol": inputs["symbol"],
        "report_period": inputs["report_period"],
        "return_model_note": inputs["return_model_note"],
        "value_range": {
            "low": round(results["core_low"]["value_per_share"]),
            "high": round(results["core_high"]["value_per_share"]),
            "currency": "HKD",
        },
        "return_model": {
            "schema_version": 1,
            "method": "annual_common_equity_irr_v1",
            "currency": "HKD",
            "model_as_of": inputs["information_cutoff"],
            "base_case_distributions_per_share": [
                round(value / inputs["diluted_shares"] * inputs["hkd_per_cny"], 4)
                for value in inputs["first_five_years"]["common_dividends"]
            ],
            "base_case_terminal_equity_value_range_per_share": {
                "year_5": {
                    "low": round(results["core_low"]["terminal_per_share"], 4),
                    "high": round(results["core_high"]["terminal_per_share"], 4),
                }
            },
        },
        "scenarios": results,
        "auxiliary_earnings_capitalization": {
            "normalized_common_operating_earnings": normalized_earnings,
            "multiples": auxiliary["multiples"],
            "value_per_share": [
                (
                    normalized_earnings * multiple
                    + 646.86
                    + inputs["common_net_cash"]
                    - inputs["operating_cash_buffer"]
                )
                * inputs["hkd_per_cny"]
                / inputs["diluted_shares"]
                for multiple in auxiliary["multiples"]
            ],
        },
        "verification": (
            "正式计算链常数现金流手算特例、延迟分配等价特例、"
            "年度现金守恒、付款能力检查通过"
        ),
    }
    (DIRECTORY / "2026-H1-output.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "value_range": result["value_range"],
                "return_model": result["return_model"],
                "scenario_values": {
                    key: round(value["value_per_share"], 2) for key, value in results.items()
                },
                "base_operating": results["reference"]["operating_projection"],
                "cash5": results["reference"]["terminal_common_net_cash"],
                "auxiliary": result["auxiliary_earnings_capitalization"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
