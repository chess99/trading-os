"""中国移动2026-Q3经营、普通股现金及证券单位模型。金额为人民币十亿元。
执行 python 2026-Q3.py，读取同目录2026-Q3-inputs.json并写简明结果。
只使用标准库。金融资产与联营收益分别计价，租赁本金在现金中扣除。
"""

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def operating_cash(row):
    ebit = sum(row["revenue"][i] * row["margin"][i] for i in range(4)) - row["central_cost"]
    profit = ebit * (1 - row["tax"]) - row["lease_interest"] - row["minority_profit"]
    cash = (
        profit + row["depreciation"] - row["capex"] - row["lease_principal"] - row["working_cash"]
    )
    return ebit, profit, cash


def present_value(cashflows, rate):
    return sum(cash / (1 + rate) ** year for year, cash in enumerate(cashflows, 1))


def finance_recovery(pool, yield_rate, rate, years):
    # 已隔离必要经营现金。分批本金实现同时减少利息本金。
    installment = pool / years
    flows = [installment + (pool - installment * year) * yield_rate for year in range(years)]
    return present_value(flows, rate)


def project(inputs, scenario):
    config = deepcopy(inputs["scenarios"][scenario])
    issued = inputs["shares"]["issued"]
    options = inputs["shares"]["options"]
    diluted = issued + sum(item["count"] for item in options)
    proceeds = sum(item["count"] * item["exercise_hkd"] * inputs["hkd_cny"] for item in options)
    cash = inputs["financial_pool_before_options"] + proceeds
    # 首期没有假定旧母公司现金可动用，新合法股利在每次付款前上划。
    parent_cash = 0.0
    parent_reserves = 0.0
    equity = inputs["opening_common_equity"] + proceeds
    rows = []
    net_operating_capital = inputs["opening_operating_capital"]
    for year, row in enumerate(config["years"], 1):
        ebit, profit, free_cash = operating_cash(row)
        interest = cash * config["financial_yield"]
        total_profit = profit + interest + row["associate_profit"]
        legal_upstream = max(
            0, profit * config["upstream_profit_share"] + interest + row["associate_dividend"]
        )
        # 本年依法新宣派金额形成母公司利润，延迟到账单独进入应收，下一期收回。
        delay = config.get("upstream_delay", [0] * 5)[year - 1]
        old_receivable = rows[-1]["parent_receivable"] if rows else 0
        upstream_received = legal_upstream * (1 - delay) + old_receivable
        parent_cost = 0.3  # 已在central_cost计入，只在母公司资金/利润桥列示
        desired_dividend = total_profit * row["payout"]
        group_funds = cash + free_cash + interest + row["associate_dividend"]
        dividend = max(
            0,
            min(
                desired_dividend,
                group_funds,
                parent_cash + upstream_received - parent_cost,
                parent_reserves + legal_upstream - parent_cost,
            ),
        )
        cash = group_funds - dividend
        parent_cash += upstream_received - parent_cost - dividend
        parent_reserves += legal_upstream - parent_cost - dividend
        equity += total_profit - dividend
        net_operating_capital += (
            row["capex"] - (row["depreciation"] - row["rou_depreciation"]) + row["working_cash"]
        )
        assert cash >= -1e-8 and parent_cash >= -1e-8 and parent_reserves >= -1e-8
        assert abs(cash - (group_funds - dividend)) < 1e-8
        assert parent_cash <= cash + inputs["necessary_cash_buffer"] + 1e-8
        rows.append(
            {
                **row,
                "year": year,
                "ebit": ebit,
                "operating_profit_common": profit,
                "free_cash": free_cash,
                "financial_income": interest,
                "common_profit": total_profit,
                "dividend": dividend,
                "dividend_per_share": dividend / diluted,
                "pool_end": cash,
                "parent_declared_income": legal_upstream,
                "parent_received": upstream_received,
                "parent_receivable": legal_upstream * delay,
                "parent_cash": parent_cash,
                "parent_reserves": parent_reserves,
                "common_equity": equity,
                "operating_capital": net_operating_capital,
            }
        )
    return {
        "scenario": scenario,
        "shares": diluted,
        "option_proceeds": proceeds,
        "rows": rows,
        "config": config,
    }


def fast_release_terminal(
    projection, rate, growth, incremental_return, recovery_years=12, permanent_cash_drag=0
):
    last = projection["rows"][-1]
    config = projection["config"]
    # 五年后现金建设负担仍高，五年渐进到成熟资本需求。过渡期现金由第五年
    # 实际FCFE向利润*(1-g/增量回报)收敛，不把第五年立即视作成熟。
    mature_cash = (
        last["operating_profit_common"] * (1 + growth) ** 5 * (1 - growth / incremental_return)
        - permanent_cash_drag
    )
    transition = [
        last["free_cash"] * (1 - year / 5) + mature_cash * year / 5 for year in range(1, 6)
    ]
    transition_capex = []
    for year, free_cash in enumerate(transition, 1):
        scale = (1 + growth) ** year
        implied_capex = (
            last["operating_profit_common"]
            + last["depreciation"]
            - last["lease_principal"]
            - last["working_cash"]
        ) * scale - free_cash
        assert implied_capex >= 0
        transition_capex.append(implied_capex)
    continuing = mature_cash * (1 + growth) / (rate - growth)
    operation = present_value(transition, rate) + continuing / (1 + rate) ** 5
    finance = finance_recovery(last["pool_end"], config["financial_yield"], rate, recovery_years)
    # 联营经营单独估值。先以实际股息量级为锚，五年过渡到45%派息，
    # 增长与留存资本回报相容，不另加累计联营留存本金。
    associate_profit = last["associate_profit"]
    associate_growth = config["associate_growth"]
    terminal_payout = config["associate_terminal_payout"]
    associate_flows = []
    current_payout = last["associate_dividend"] / associate_profit
    for year in range(1, 6):
        payout = current_payout + (terminal_payout - current_payout) * year / 5
        associate_flows.append(associate_profit * (1 + associate_growth) ** year * payout)
    associate_tail = associate_flows[-1] * (1 + growth) / (rate - growth)
    associate = present_value(associate_flows, rate) + associate_tail / (1 + rate) ** 5
    total = operation + finance + associate
    return {
        "operation": operation,
        "finance": finance,
        "associate": associate,
        "total": total,
        "per_share": total / projection["shares"],
        "transition_cash": transition,
        "mature_cash": mature_cash,
        "transition_implied_capex": transition_capex,
        "associate_implied_incremental_roe": associate_growth / (1 - terminal_payout),
    }


def stable_policy_value(cash, profit, free_cash, rate, growth, financial_yield, payout):
    """稳定期合并现金状态的解析解。达到资金上限时下调分配，不借款补股利。

    profit/free_cash分别为当年经营加联营权益利润、经营加联营实收现金。
    稳定期它们按同一名义增长率增长。现金递推为a*C+q*(F-p*E)。
    如目标分配会耗尽资金，解析定位耗尽时点，之后仅支付可实现现金。
    """
    q = 1 + growth
    a = 1 + financial_yield * (1 - payout)
    b = free_cash - payout * profit
    cash_coefficient = payout * financial_yield / (rate - financial_yield * (1 - payout))
    unconstrained = cash_coefficient * cash + q * (
        payout * (1 - cash_coefficient) * profit + cash_coefficient * free_cash
    ) / (rate - growth)
    if b >= 0:
        return {
            "value": unconstrained,
            "depletion_year": None,
            "cash_coefficient": cash_coefficient,
        }

    def balance(year):
        return a**year * cash + q * b * (a**year - q**year) / (a - q)

    right = 1
    while right < 4096 and balance(right) > 0:
        right *= 2
    if balance(right) > 0:
        return {
            "value": unconstrained,
            "depletion_year": None,
            "cash_coefficient": cash_coefficient,
        }
    left = 0
    while right - left > 1:
        middle = (left + right) // 2
        if balance(middle) > 0:
            left = middle
        else:
            right = middle
    depletion_year = right
    before = depletion_year - 1
    discount = 1 + rate

    def geometric_sum(ratio, periods):
        return (1 - ratio**periods) / (1 - ratio)

    a_part = cash + q * b / (a - q)
    q_part = -q * b / (a - q)
    value = payout * profit * q / discount * geometric_sum(q / discount, before)
    value += (
        payout
        * financial_yield
        / discount
        * (
            a_part * geometric_sum(a / discount, before)
            + q_part * geometric_sum(q / discount, before)
        )
    )
    final_payment = balance(before) * (1 + financial_yield) + free_cash * q**depletion_year
    ongoing = free_cash * q ** (depletion_year + 1) / (rate - growth)
    value += (final_payment + ongoing) / discount**depletion_year
    return {"value": value, "depletion_year": depletion_year, "cash_coefficient": cash_coefficient}


def terminal_value(
    projection, rate, growth, incremental_return, permanent_cash_drag=0, policy="ordinary_80"
):
    last = projection["rows"][-1]
    config = projection["config"]
    cash = last["pool_end"]
    final_profit = last["operating_profit_common"]
    final_associate = last["associate_profit"]
    mature_cash = (
        final_profit * (1 + growth) ** 5 * (1 - growth / incremental_return) - permanent_cash_drag
    )
    final_payout = config.get("long_run_payout", 0.8)
    payout_path = [final_payout] * 5
    if policy == "gradual_90":
        payout_path = [0.82, 0.84, 0.86, 0.88, 0.90]
    flows = []
    rows = []
    for year, payout in enumerate(payout_path, 1):
        operating_profit = final_profit * (1 + growth) ** year
        operating_free_cash = last["free_cash"] * (1 - year / 5) + mature_cash * year / 5
        associate_profit = final_associate * (1 + config["associate_growth"]) ** year
        associate_payout = (
            last["associate_dividend"] / final_associate
            + (config["associate_terminal_payout"] - last["associate_dividend"] / final_associate)
            * year
            / 5
        )
        associate_cash = associate_profit * associate_payout
        finance_income = cash * config["financial_yield"]
        total_profit = operating_profit + associate_profit + finance_income
        available = cash + operating_free_cash + associate_cash + finance_income
        dividend = min(total_profit * payout, available)
        cash = available - dividend
        implied_capex = (
            final_profit + last["depreciation"] - last["lease_principal"] - last["working_cash"]
        ) * (1 + growth) ** year - operating_free_cash
        assert cash >= -1e-8 and implied_capex >= 0
        flows.append(dividend)
        rows.append(
            {
                "year": year + 5,
                "operating_profit": operating_profit,
                "operating_free_cash": operating_free_cash,
                "associate_profit": associate_profit,
                "associate_cash": associate_cash,
                "finance_income": finance_income,
                "dividend": dividend,
                "dividend_per_share": dividend / projection["shares"],
                "pool_end": cash,
                "implied_capex": implied_capex,
            }
        )
    steady = stable_policy_value(
        cash,
        operating_profit + associate_profit,
        operating_free_cash + associate_cash,
        rate,
        growth,
        config["financial_yield"],
        payout_path[-1],
    )
    total = present_value(flows, rate) + steady["value"] / (1 + rate) ** 5
    return {
        "total": total,
        "per_share": total / projection["shares"],
        "policy": policy,
        "transition_rows": rows,
        "mature_cash": mature_cash,
        "stable_policy": steady,
        "year_6_distribution_per_share": rows[0]["dividend_per_share"],
        "year_5_to_6_distribution_change": rows[0]["dividend"] / last["dividend"] - 1,
    }


def valuation(projection, endpoint):
    terminal = terminal_value(projection, **endpoint)
    rate = endpoint["rate"]
    dividends = [row["dividend_per_share"] for row in projection["rows"]]
    terminal_pv = terminal["per_share"] / (1 + rate) ** 5
    return {
        "current": present_value(dividends, rate) + terminal_pv,
        "terminal": terminal,
        "terminal_present_value_fraction": terminal_pv
        / (present_value(dividends, rate) + terminal_pv),
    }


def validate_math():
    row = {
        "revenue": [100, 0, 0, 0],
        "margin": [0.2, 0, 0, 0],
        "central_cost": 0,
        "tax": 0.25,
        "lease_interest": 1,
        "minority_profit": 0,
        "depreciation": 10,
        "capex": 8,
        "lease_principal": 2,
        "working_cash": 1,
    }
    assert operating_cash(row) == (20, 14, 13)
    assert abs(present_value([10, 11], 0.1) - (10 / 1.1 + 11 / 1.21)) < 1e-12
    assert abs(finance_recovery(100, 0, 0, 2) - 100) < 1e-12
    assert abs(finance_recovery(100, 0.02, 0.1, 2) - (52 / 1.1 + 51 / 1.21)) < 1e-12
    assert (
        abs(stable_policy_value(100, 0, 0, 0.1, 0, 0.02, 0.8)["value"] - 1.6 / (0.1 - 0.004))
        < 1e-10
    )
    assert abs(stable_policy_value(0, 10, 5, 0.1, 0, 0.02, 0.8)["value"] - 50) < 1e-10


def calculate(inputs):
    validate_math()
    projections = {name: project(inputs, name) for name in inputs["scenarios"]}
    base = projections["base"]
    low = valuation(base, inputs["core_endpoints"]["low"])
    high = valuation(base, inputs["core_endpoints"]["high"])
    central = valuation(base, inputs["central_endpoint"])
    scenarios = {
        name: valuation(
            projections[name], inputs["scenario_endpoints"].get(name, inputs["central_endpoint"])
        )
        for name in projections
    }
    sensitivities = {}
    for label, delta in [("annual_capex_plus_10", 10), ("annual_capex_minus_10", -10)]:
        changed = deepcopy(inputs)
        for row in changed["scenarios"]["base"]["years"]:
            row["capex"] += delta
        sensitivities[label] = valuation(project(changed, "base"), inputs["central_endpoint"])[
            "current"
        ]
    changed = deepcopy(inputs)
    for row in changed["scenarios"]["base"]["years"]:
        row["capex"] += 10
    persistent = dict(inputs["central_endpoint"], permanent_cash_drag=10)
    sensitivities["annual_capex_plus_10_permanent"] = valuation(
        project(changed, "base"), persistent
    )["current"]
    changed = deepcopy(inputs)
    changed["scenarios"]["base"]["upstream_delay"] = [0.3, 0, 0, 0, 0]
    delayed_upstream = project(changed, "base")
    sensitivities["upstream_delay_30pct_first_dividend"] = delayed_upstream["rows"][0][
        "dividend_per_share"
    ]
    fx = inputs["hkd_cny"]
    dps = [round(row["dividend_per_share"], 4) for row in base["rows"]]
    outputs = {}
    for symbol, currency, divisor in [("CN:600941", "CNY", 1), ("HK:00941", "HKD", fx)]:
        value = {
            "low": round(low["current"] / divisor, 2),
            "high": round(high["current"] / divisor, 2),
            "currency": currency,
        }
        model = {
            "schema_version": 1,
            "method": "annual_common_equity_irr_v1",
            "currency": currency,
            "model_as_of": inputs["information_cutoff"],
            "base_case_distributions_per_share": [
                round(row["dividend_per_share"] / divisor, 4) for row in base["rows"]
            ],
            "base_case_terminal_equity_value_range_per_share": {
                "year_5": {
                    "low": round(low["terminal"]["per_share"] / divisor, 2),
                    "high": round(high["terminal"]["per_share"] / divisor, 2),
                }
            },
        }
        outputs[symbol] = {
            "symbol": symbol,
            "report_period": "2026-Q3",
            "value_range": value,
            "return_model": model,
        }
    # 同一已采用利润路径的辅助整体PE，不再重复添加金融本金。
    normalized_profit = sum(row["common_profit"] for row in base["rows"]) / 5
    auxiliary = {
        "low": normalized_profit * 10 / base["shares"],
        "high": normalized_profit * 12 / base["shares"],
    }
    policy_comparison = {}
    for policy in ["ordinary_80", "gradual_90"]:
        endpoint = dict(inputs["central_endpoint"], policy=policy)
        policy_comparison[policy] = valuation(base, endpoint)
    fast = fast_release_terminal(
        base, recovery_years=inputs["fast_release_years"], **inputs["central_endpoint"]
    )
    first_assoc_cash = (
        base["rows"][-1]["associate_profit"] * 1.02 * (6.8 / 16.2 + (0.45 - 6.8 / 16.2) / 5)
    )
    first_finance_cash = base["rows"][-1]["pool_end"] * (0.02 + 1 / inputs["fast_release_years"])
    first = (fast["transition_cash"][0] + first_assoc_cash + first_finance_cash) / base["shares"]
    policy_comparison["fast_release"] = {
        "current": present_value(dps, inputs["central_endpoint"]["rate"])
        + fast["per_share"] / (1 + inputs["central_endpoint"]["rate"]) ** 5,
        "terminal": fast,
        "year_6_distribution_per_share": first,
        "year_5_to_6_distribution_change": first / base["rows"][-1]["dividend_per_share"] - 1,
    }
    selected = outputs[inputs.get("symbol", "CN:600941")]
    return {
        **selected,
        "return_model_note": inputs["return_model_note"],
        "outputs": outputs,
        "core": {"low": low, "high": high, "central": central},
        "auxiliary": auxiliary,
        "policy_comparison": policy_comparison,
        "scenarios": scenarios,
        "sensitivities": sensitivities,
        "projections": {
            name: {k: v for k, v in projection.items() if k != "config"}
            for name, projection in projections.items()
        },
        "math_checks": "operating cash, timing and financial principal known-case tests passed",
    }


if __name__ == "__main__":
    inputs = json.loads((ROOT / "2026-Q3-inputs.json").read_text())
    result = calculate(inputs)
    (ROOT / "2026-Q3-output.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "outputs": result["outputs"],
                "auxiliary": result["auxiliary"],
                "scenarios": {k: round(v["current"], 2) for k, v in result["scenarios"].items()},
                "sensitivities": result["sensitivities"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
