"""宁波银行普通股股利/权益模型。金额百万元，python 2026-Q3.py 可复算。"""

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = json.loads((ROOT / "2026-Q3-input.json").read_text())


def equity_cashflows(book, roes, payouts, discount, terminal_roe, growth):
    """清洁盈余、期末支付及稳态银行权益公式，共用正式估值计算链。"""
    start = book
    rows = []
    for year, (roe, payout) in enumerate(zip(roes, payouts, strict=True), 1):
        opening = book
        earnings = opening * roe
        dividend = earnings * payout
        book = opening + earnings - dividend
        rows.append(
            {
                "year": year,
                "opening_book": opening,
                "roe": roe,
                "earnings": earnings,
                "payout": payout,
                "dividend": dividend,
                "book": book,
            }
        )
        assert abs(book - opening - earnings + dividend) < 1e-7
    terminal = book * (terminal_roe - growth) / (discount - growth)
    pv_dividends = sum(row["dividend"] / (1 + discount) ** row["year"] for row in rows)
    value = pv_dividends + terminal / (1 + discount) ** len(rows)
    residual = start + sum(
        (row["earnings"] - discount * row["opening_book"]) / (1 + discount) ** row["year"]
        for row in rows
    )
    residual += (terminal - book) / (1 + discount) ** len(rows)
    assert abs(value - residual) < 1e-7
    return {
        "rows": rows,
        "terminal_10": terminal,
        "value": value,
        "residual_value": residual,
        "terminal_pv_share": terminal / (1 + discount) ** len(rows) / value,
    }


def run(discount=0.105, terminal_roe=0.115, scenario="base"):
    p = deepcopy(INPUT)
    paid = p["paid_interim_dps"] * p["shares_million"] + p["declared_preference_dividend"]
    book = p["reported_common_equity"] - paid
    group_cet = p["group_cet1"] - paid
    bank_cet = p["bank_cet1"] - paid
    legal_profit = p["bank_retained_profit"] - paid
    group_rwa = p["group_rwa"]
    bank_rwa = p["bank_rwa"]
    roes = p["base_roe"] + [
        p["base_roe"][-1] + (terminal_roe - p["base_roe"][-1]) * i / 5 for i in range(1, 6)
    ]
    payouts = p["base_payout"] + [0.40, 0.47, 0.54, 0.62, 1 - p["steady_growth"] / terminal_roe]
    growth = p["steady_growth"]
    if scenario == "cycle":
        roes[:3] = [0.10, 0.105, 0.122]
        payouts[:2] = [0.20, 0.25]
        p["rwa_growth"][:3] = [0.04, 0.04, 0.06]
    elif scenario == "structural":
        # 第一年前扣已识别新增信用损失，随后定价、融资和新增贷款经济性永久受损。
        loss = book * 0.05
        book -= loss
        group_cet -= loss
        bank_cet -= loss * 0.85
        legal_profit -= loss * 0.85
        roes = [0.075, 0.08, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085, 0.085]
        terminal_roe = 0.085
        growth = 0.025
        discount = 0.115
        payouts = [0.10, 0.20, 0.30, 0.35, 0.40, 0.45, 0.50, 0.57, 0.63, 1 - growth / terminal_roe]
        p["rwa_growth"] = [0, 0.02, 0.025, 0.025, 0.025, 0.025, 0.025, 0.025, 0.025, 0.025]
    elif scenario == "strong":
        roes[:5] = [0.14, 0.14, 0.138, 0.135, 0.132]
        roes[5:] = [0.13, 0.128, 0.127, 0.126, 0.125]
        terminal_roe = 0.125
        discount = 0.10
        payouts[-1] = 1 - growth / terminal_roe
        p["rwa_growth"][:5] = [0.085, 0.085, 0.08, 0.07, 0.06]
    answer = equity_cashflows(book, roes, payouts, discount, terminal_roe, growth)
    for row, desired_growth, upstream_fraction in zip(
        answer["rows"], p["rwa_growth"], p["subsidiary_upstream_fraction"], strict=True
    ):
        earnings = row["earnings"]
        cash = row["dividend"]
        # 子公司实际归母利润的上划预算，仅进入母行，集团不重复计利润。
        bank_operating = earnings * p["bank_profit_share"]
        upstream = earnings * (1 - p["bank_profit_share"]) * upstream_fraction
        bank_profit = bank_operating + upstream
        group_cet += earnings - cash
        bank_cet += bank_profit - cash
        # 资本缓冲是模型经营选择；资本不足时降扩表，无外源普通股增发。
        allowed_group = group_cet / 0.0925
        allowed_bank = bank_cet / 0.0875
        actual_growth = min(
            desired_growth, allowed_group / group_rwa - 1, allowed_bank / bank_rwa - 1
        )
        assert actual_growth >= -1e-10, "初始资本无法在不缩表下支持该情景"
        reserve = p["bank_general_reserve"] * actual_growth
        legal_profit += bank_profit - bank_operating * 0.10 - reserve - cash
        p["bank_general_reserve"] += reserve
        group_rwa *= 1 + actual_growth
        bank_rwa *= 1 + actual_growth
        assert (
            abs(
                p["bank_general_reserve"] / bank_rwa
                - INPUT["bank_general_reserve"] / INPUT["bank_rwa"]
            )
            < 1e-12
        )
        assert legal_profit >= 0
        assert bank_cet / bank_rwa >= 0.0875 - 1e-10
        assert group_cet / group_rwa >= 0.0925 - 1e-10
        assert (bank_cet + p["other_tier1"]) / bank_rwa >= 0.0875
        assert (group_cet + p["other_tier1"]) / group_rwa >= 0.0875
        assert (bank_cet + p["other_tier1"] + p["bank_tier2"]) / bank_rwa >= 0.1075
        assert (group_cet + p["other_tier1"] + p["group_tier2"]) / group_rwa >= 0.1075
        row.update(
            {
                "dps": cash / p["shares_million"],
                "bvps": row["book"] / p["shares_million"],
                "rwa_growth": actual_growth,
                "group_rwa": group_rwa,
                "bank_rwa": bank_rwa,
                "group_cet_ratio": group_cet / group_rwa,
                "bank_cet_ratio": bank_cet / bank_rwa,
                "bank_common_profit": bank_profit,
                "subsidiary_cash_received": upstream,
                "bank_distributable_profit": legal_profit,
                "bank_general_reserve": p["bank_general_reserve"],
                "bank_general_reserve_addition": reserve,
            }
        )
    answer["value_per_share"] = answer["value"] / p["shares_million"]
    answer["terminal_year5_per_share"] = (
        sum(r["dividend"] / (1 + discount) ** (r["year"] - 5) for r in answer["rows"][5:])
        + answer["terminal_10"] / (1 + discount) ** 5
    ) / p["shares_million"]
    answer["discount"] = discount
    answer["terminal_roe"] = terminal_roe
    answer["steady_growth"] = growth
    answer["terminal_payout"] = 1 - growth / terminal_roe
    answer["opening_bvps"] = book / p["shares_million"]
    return answer


def policy_value(productive, surplus, roe, payout, growth, cash_yield, discount):
    """双资本稳态解析解，含所有未来分红、利息及仍留存本金的经济后果。"""
    surplus_factor = payout * cash_yield / (discount - (1 - payout) * cash_yield)
    productive_factor = (payout * roe + surplus_factor * ((1 - payout) * roe - growth)) / (
        discount - growth
    )
    return productive * productive_factor + surplus * surplus_factor


def run_policy(discount=0.105, terminal_roe=0.115, terminal_payout=0.50, scenario="base"):
    initial = run(discount, terminal_roe, scenario)
    rows = deepcopy(initial["rows"][:5])
    discount = initial["discount"]
    if scenario == "structural":
        terminal_roe = 0.085
    if scenario == "strong":
        terminal_roe = 0.125
    growth = initial["steady_growth"]
    cash_yield = 0.02
    productive = rows[-1]["book"]
    surplus = 0.0
    group_rwa = rows[-1]["group_rwa"]
    bank_rwa = rows[-1]["bank_rwa"]
    group_cet = rows[-1]["group_cet_ratio"] * group_rwa
    bank_cet = rows[-1]["bank_cet_ratio"] * bank_rwa
    legal_profit = rows[-1]["bank_distributable_profit"]
    general_reserve = rows[-1]["bank_general_reserve"]
    for offset in range(1, 6):
        year = offset + 5
        roe = rows[4]["roe"] + (terminal_roe - rows[4]["roe"]) * offset / 5
        payout = rows[4]["payout"] + (terminal_payout - rows[4]["payout"]) * offset / 5
        productive_growth = [0.065, 0.055, 0.045, 0.04, 0.035][offset - 1]
        if scenario == "structural":
            productive_growth = 0.025
        opening = productive + surplus
        operating_earnings = productive * roe
        cash_income = surplus * cash_yield
        earnings = operating_earnings + cash_income
        dividend = earnings * payout
        required_retention = productive * productive_growth
        next_surplus = surplus + earnings - dividend - required_retention
        assert next_surplus >= -1e-8
        productive += required_retention
        surplus = max(0, next_surplus)
        group_cet += earnings - dividend
        upstream_fraction = INPUT["subsidiary_upstream_fraction"][year - 1]
        upstream = earnings * 0.18 * upstream_fraction
        bank_profit = earnings * 0.82 + upstream
        bank_cet += bank_profit - dividend
        reserve = general_reserve * productive_growth
        general_reserve += reserve
        legal_profit += bank_profit - earnings * 0.82 * 0.10 - reserve - dividend
        group_rwa *= 1 + productive_growth
        bank_rwa *= 1 + productive_growth
        assert (
            abs(general_reserve / bank_rwa - INPUT["bank_general_reserve"] / INPUT["bank_rwa"])
            < 1e-12
        )
        assert bank_cet / bank_rwa >= 0.0875 and group_cet / group_rwa >= 0.0925
        assert legal_profit > 0
        for capital, rwa, tier2 in [
            (group_cet, group_rwa, INPUT["group_tier2"]),
            (bank_cet, bank_rwa, INPUT["bank_tier2"]),
        ]:
            assert (capital + INPUT["other_tier1"]) / rwa >= 0.0875
            assert (capital + INPUT["other_tier1"] + tier2) / rwa >= 0.1075
        row = {
            "year": year,
            "opening_book": opening,
            "book": productive + surplus,
            "roe": earnings / opening,
            "operating_roe": roe,
            "earnings": earnings,
            "payout": payout,
            "dividend": dividend,
            "productive_book": productive,
            "surplus": surplus,
            "cash_income": cash_income,
            "dps": dividend / INPUT["shares_million"],
            "bvps": (productive + surplus) / INPUT["shares_million"],
            "rwa_growth": productive_growth,
            "group_rwa": group_rwa,
            "bank_rwa": bank_rwa,
            "group_cet_ratio": group_cet / group_rwa,
            "bank_cet_ratio": bank_cet / bank_rwa,
            "bank_distributable_profit": legal_profit,
            "bank_common_profit": bank_profit,
            "bank_general_reserve": general_reserve,
            "bank_general_reserve_addition": reserve,
            "subsidiary_cash_received": upstream,
        }
        assert abs(row["book"] - opening - earnings + dividend) < 1e-7
        rows.append(row)
    # 稳态只需量级不等式。忽略额外资金利息可得到资本和法定利润留存下界。
    # P、RWA、一般准备此后均按g增长，故同一不等式适用于之后各年。
    bank_income_share = (
        INPUT["bank_profit_share"]
        + (1 - INPUT["bank_profit_share"]) * INPUT["subsidiary_upstream_fraction"][-1]
    )
    operating_profit_floor = productive * terminal_roe
    bank_capital_retention_floor = (bank_income_share - terminal_payout) * operating_profit_floor
    bank_total_capital_growth_requirement = bank_rwa * growth * 0.1075
    legal_profit_increase_floor = (
        bank_income_share - terminal_payout - INPUT["bank_profit_share"] * 0.10
    ) * operating_profit_floor - general_reserve * growth
    assert bank_capital_retention_floor >= bank_total_capital_growth_requirement
    assert legal_profit_increase_floor > 0
    steady_bank_check = {
        "income_share_after_subsidiary_remittance": bank_income_share,
        "annual_retention_floor": bank_capital_retention_floor,
        "annual_total_capital_growth_requirement": bank_total_capital_growth_requirement,
        "annual_legal_profit_increase_floor": legal_profit_increase_floor,
        "basis": (
            "成熟期忽略额外资金利息的下界；P/RWA/一般准备同比例增长，"
            "保留现有一级及二级资本正常续作。"
        ),
    }
    terminal = policy_value(
        productive, surplus, terminal_roe, terminal_payout, growth, cash_yield, discount
    )
    value = (
        sum(r["dividend"] / (1 + discount) ** r["year"] for r in rows)
        + terminal / (1 + discount) ** 10
    )
    residual = (
        rows[0]["opening_book"]
        + sum(
            (r["earnings"] - discount * r["opening_book"]) / (1 + discount) ** r["year"]
            for r in rows
        )
        + (terminal - rows[-1]["book"]) / (1 + discount) ** 10
    )
    assert abs(value - residual) < 1e-7
    tv5 = (
        sum(r["dividend"] / (1 + discount) ** (r["year"] - 5) for r in rows[5:])
        + terminal / (1 + discount) ** 5
    )
    return {
        "rows": rows,
        "value_per_share": value / INPUT["shares_million"],
        "terminal_year5_per_share": tv5 / INPUT["shares_million"],
        "terminal_pv_share": terminal / (1 + discount) ** 10 / value,
        "opening_bvps": initial["opening_bvps"],
        "discount": discount,
        "terminal_roe": terminal_roe,
        "steady_growth": growth,
        "terminal_payout": terminal_payout,
        "cash_yield": cash_yield,
        "terminal_10": terminal,
        "value": value,
        "steady_bank_check": steady_bank_check,
    }


def main():
    # 正式计算链手算特例，ROE等于资本成本时任何有界留存均应等于初始账面。
    special = equity_cashflows(100, [0.10] * 10, [0.50] * 10, 0.10, 0.10, 0.05)
    assert abs(special["value"] - 100) < 1e-10
    # 无增长全分配，利润10，资本成本10%，价值100。
    special2 = equity_cashflows(100, [0.10] * 10, [1.0] * 10, 0.10, 0.10, 0)
    assert abs(special2["value"] - 100) < 1e-10
    # 稳态手算特例，通过正式双资本终值函数。
    assert abs(policy_value(100, 20, 0.10, 0.50, 0.05, 0.10, 0.10) - 120) < 1e-9
    assert abs(policy_value(100, 0, 0.10, 1.0, 0, 0.02, 0.10) - 100) < 1e-9
    low = run_policy(0.11, 0.11, 0.45)
    high = run_policy(0.10, 0.12, 0.55)
    base = run_policy()
    b = base["opening_bvps"]
    auxiliary = [b * (0.11 - 0.035) / (0.11 - 0.035), b * (0.12 - 0.035) / (0.10 - 0.035)]
    output = {
        "symbol": INPUT["symbol"],
        "report_period": INPUT["report_period"],
        "value_range": {
            "low": round(low["value_per_share"], 1),
            "high": round(high["value_per_share"], 1),
            "currency": "CNY",
        },
        "return_model": {
            "schema_version": 1,
            "method": "annual_common_equity_irr_v1",
            "currency": "CNY",
            "model_as_of": INPUT["information_cutoff"],
            "base_case_distributions_per_share": [round(r["dps"], 6) for r in base["rows"][:5]],
            "base_case_terminal_equity_value_range_per_share": {
                "year_5": {
                    "low": round(low["terminal_year5_per_share"], 6),
                    "high": round(high["terminal_year5_per_share"], 6),
                }
            },
        },
        "core_low": low,
        "core_high": high,
        "base": base,
        "auxiliary_current_pb_roe": auxiliary,
        "cycle": run_policy(scenario="cycle"),
        "structural": run_policy(scenario="structural"),
        "strong": run_policy(terminal_payout=0.60, scenario="strong"),
        "discount_plus_1pct": run_policy(0.115),
        "terminal_roe_minus_1pct": run_policy(0.105, 0.105),
        "payout_40": run_policy(terminal_payout=0.40),
        "payout_50": run_policy(terminal_payout=0.50),
        "payout_60": run_policy(terminal_payout=0.60),
        "return_model_note": (
            "未来五年现金按30%-35%普通股利润预算，股数6603590792不变。"
            "Y5终值从55.6113元权益开始，分开生产性资本与额外留存，"
            "Y6-10逐步提高派息至45%-55%，生产性资本增速降至3.5%，"
            "长期ROE11%-12%，多余资金2%税后收益，未假设额外本金一次释放。"
            "普通和优先股已知分配从起点扣除，已付0.4元不在未来现金重复。"
            "母行一般准备由前五年余额接续逐年滚动，"
            "成熟期留存覆盖按3.5%增长所需总资本及法定准备。"
        ),
        "tests": (
            "4 hand-computable cases, clean-surplus reconciliation, "
            "capital and legal-profit checks passed"
        ),
    }
    (ROOT / "2026-Q3-output.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                key: output[key]
                for key in ["value_range", "return_model", "auxiliary_current_pb_roe", "tests"]
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    for name in [
        "base",
        "core_low",
        "core_high",
        "cycle",
        "structural",
        "strong",
        "discount_plus_1pct",
        "terminal_roe_minus_1pct",
    ]:
        r = output[name]
        print(
            name,
            round(r["value_per_share"], 4),
            round(r["terminal_pv_share"] * 100, 2),
            round(r["terminal_year5_per_share"], 4),
        )


if __name__ == "__main__":
    main()
