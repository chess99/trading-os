"""茅台长期研究样稿的条件模型；金额单位亿元，股数单位亿股。

独立说明用，不读取或修改研究状态，不产生实时价格、交易触发器或正式估值。
python3 model.py 重新生成同目录 model-output.json。
"""

from dataclasses import dataclass, replace
import json
from pathlib import Path


SHARES = 12.50081601
PARKED_CASH_YIELD = 0.015  # 税后名义收益率，估计而非承诺


@dataclass(frozen=True)
class Scenario:
    earnings: tuple[float, ...]  # 未来十年，剔除金融资产收益后的归普通股经营利润
    incremental_return: float
    terminal_growth: float
    payout_budget: float = 0.80


SCENARIOS = {
    "base": Scenario((800, 800) + tuple(800 * 1.035**i for i in range(1, 9)), .25, .03),
    "cyclical_weak": Scenario((680, 720, 780, 800) + tuple(800 * 1.035**i for i in range(1, 7)), .25, .03),
    "structural_weak": Scenario((720, 660, 600, 560, 540, 530, 525, 520, 515, 510), .15, 0),
    "upside": Scenario((820, 860) + tuple(860 * 1.06**i for i in range(1, 9)), .30, .025),
}


def evaluate(scenario, discount_rate, initial_releasable_assets=0,
             cash_recovery=1, terminal_realization=1):
    """经营利润不含单列现金收益；留存现金滚存到第十年后只回收一次。

    当年投入支持下一年增量利润。经济维护投入假设已由折旧覆盖；
    incremental_return 同时约束成长性固定资本与营运资本。
    负增长不自动释放既有资本，分红不借债，期末金融资产回收率可单独压力测试。
    终值是第十一年以后经营现金的现值，不是预设退出PE。
    """
    assert len(scenario.earnings) == 10
    assert discount_rate > scenario.terminal_growth
    assert 0 <= scenario.terminal_growth < scenario.incremental_return
    next_earnings = scenario.earnings[1:] + (scenario.earnings[-1] * (1 + scenario.terminal_growth),)
    cash = initial_releasable_assets
    rows = []
    dividend_pv = 0
    for year, (earnings, next_profit) in enumerate(zip(scenario.earnings, next_earnings), 1):
        opening_cash = cash
        growth_investment = max(next_profit - earnings, 0) / scenario.incremental_return
        distributable = earnings - growth_investment
        assert distributable >= 0, "该路径需要另建融资预算，不能静默挪用现金"
        dividend = min(scenario.payout_budget * earnings, distributable)
        interest = opening_cash * PARKED_CASH_YIELD
        cash = opening_cash + interest + distributable - dividend
        dividend_pv += dividend / (1 + discount_rate)**year
        rows.append({
            "year": year, "operating_common_earnings": earnings,
            "next_year_operating_common_earnings": next_profit,
            "growth_investment": growth_investment,
            "distributable_operating_cash": distributable,
            "common_dividend": dividend,
            "common_dividend_per_share": dividend / SHARES,
            "opening_parked_cash": opening_cash, "parked_cash_interest": interest,
            "closing_parked_cash": cash,
        })
    terminal_payout = 1 - scenario.terminal_growth / scenario.incremental_return
    terminal_operating_value = next_earnings[-1] * terminal_payout / (discount_rate - scenario.terminal_growth)
    terminal_operating_value *= terminal_realization
    terminal_operating_pv = terminal_operating_value / (1 + discount_rate)**10
    cash_pv = cash * cash_recovery / (1 + discount_rate)**10
    total_pv = dividend_pv + terminal_operating_pv + cash_pv
    return {
        "discount_rate": discount_rate,
        "initial_releasable_assets": initial_releasable_assets,
        "value_per_share": total_pv / SHARES,
        "dividend_pv_per_share": dividend_pv / SHARES,
        "terminal_operating_pv_per_share": terminal_operating_pv / SHARES,
        "terminal_cash_pv_per_share": cash_pv / SHARES,
        "terminal_share_of_pv": (terminal_operating_pv + cash_pv) / total_pv,
        "year_10_operating_earnings": scenario.earnings[-1],
        "year_10_parked_cash": cash,
        "year_10_terminal_operating_value_per_share": terminal_operating_value / SHARES,
        "terminal_payout": terminal_payout,
        "ten_year_dividends_per_share": sum(row["common_dividend"] for row in rows) / SHARES,
        "rows": rows,
    }


def verify():
    """验证现金守恒、权益重复计量边界和一组可独立手算的稳态。"""
    for scenario in SCENARIOS.values():
        result = evaluate(scenario, .09)
        for row in result["rows"]:
            assert abs(row["opening_parked_cash"] + row["parked_cash_interest"]
                       + row["operating_common_earnings"] - row["growth_investment"]
                       - row["common_dividend"] - row["closing_parked_cash"]) < 1e-8
    flat = Scenario((800,) * 10, .25, 0, 1)
    assert abs(evaluate(flat, .10)["value_per_share"] - 800 / .10 / SHARES) < 1e-8
    base = SCENARIOS["base"]
    a = evaluate(base, .09)
    b = evaluate(base, .09, initial_releasable_assets=1000)
    assert abs((b["value_per_share"] - a["value_per_share"])
               - 1000 * 1.015**10 / 1.09**10 / SHARES) < 1e-8
    assert evaluate(base, .09, cash_recovery=.5)["value_per_share"] < a["value_per_share"]
    assert evaluate(base, .10)["value_per_share"] < a["value_per_share"]


def holder_willing_price(scenario, target_return, terminal_capital_cost=.09):
    """决策演示：固定第十年经营终值的资本成本，再改变持有人的要求回报。

    避免个人目标回报升高时，偷偷同时下调作为公司研究输入的未来终值。
    十年末价值兑现仍是条件；没有声称市场当时一定接受该价格。
    """
    reference = evaluate(scenario, terminal_capital_cost)
    terminal = (reference["year_10_terminal_operating_value_per_share"]
                + reference["year_10_parked_cash"] / SHARES)
    return (sum(row["common_dividend_per_share"] / (1 + target_return)**row["year"]
                for row in reference["rows"])
            + terminal / (1 + target_return)**10)


def main():
    verify()
    def compact(result):
        return {key: value for key, value in result.items() if key != "rows"}

    output = {
        "purpose": "long_term_research_sample_not_canonical_valuation",
        "financial_information_cutoff": "2026-08-15",
        "units": {"money": "CNY_100m", "shares": "100m", "per_share": "CNY"},
        "shares": SHARES,
        "holder_willing_prices_fixed_9pct_terminal_cost": {
            name: {str(rate): holder_willing_price(s, rate) for rate in (.08, .09, .10, .12)}
            for name, s in SCENARIOS.items()
        },
        "annual_paths": {name: evaluate(s, .09)["rows"] for name, s in SCENARIOS.items()},
        "scenario_values": {name: [compact(evaluate(s, r)) for r in (.08, .085, .09, .10, .12)]
                            for name, s in SCENARIOS.items()},
        "sensitivities_at_9pct": {
            "base": evaluate(SCENARIOS["base"], .09),
            "terminal_growth_2pct": evaluate(replace(SCENARIOS["base"], terminal_growth=.02), .09),
            "incremental_return_15pct": evaluate(replace(SCENARIOS["base"], incremental_return=.15), .09),
            "half_recovery_of_new_parked_cash": evaluate(SCENARIOS["base"], .09, cash_recovery=.5),
            "release_extra_1000_at_year10": evaluate(SCENARIOS["base"], .09, initial_releasable_assets=1000),
            "permanent_20pct_operating_cash_leakage": evaluate(SCENARIOS["base"], .09, terminal_realization=.8),
        },
    }
    output["sensitivities_at_9pct"] = {
        name: compact(result) for name, result in output["sensitivities_at_9pct"].items()
    }
    path = Path(__file__).with_name("model-output.json")
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    for name, results in output["scenario_values"].items():
        print(name, [(x["discount_rate"], round(x["value_per_share"], 1)) for x in results])
    for name, result in output["sensitivities_at_9pct"].items():
        print(name, round(result["value_per_share"], 1))
    print("cash conservation and independent steady-state checks: passed")


if __name__ == "__main__":
    main()
