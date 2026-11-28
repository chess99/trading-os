"""宏远股份普通股模型。执行本文件，读取同目录输入并重新生成同期结果。"""

import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def present_value(payments, year_five_value, rate):
    """普通股现金分配在每年期末发生，第五年终值为除息后余额。"""
    n = len(payments)
    return (
        sum(p / (1 + rate) ** i for i, p in enumerate(payments, 1))
        + year_five_value / (1 + rate) ** n
    )


def run_path(facts, path, revenue, gross):
    shares = facts["shares"]
    volume_prior = 1
    carried_cash = 0
    years = []
    for volume, unit, net_fixed, extra in zip(
        path["volume"],
        path["unit_gross"],
        path["net_fixed_investment"],
        path["extra_cash_tied"],
        strict=True,
    ):
        normal_income = gross * volume * unit * path["net_capture"]
        income = normal_income - max(-carried_cash, 0) * path["funding_rate"]
        working = max(0, volume - volume_prior) * revenue * path["working_intensity"] + extra
        owner_cash = income - net_fixed - working
        dividend = max(0, min(income * path["payout"], carried_cash + owner_cash))
        closing = carried_cash + owner_cash - dividend
        assert isclose(
            closing + dividend - carried_cash, income - net_fixed - working, abs_tol=1e-8
        )
        years.append(
            dict(
                net_income=income,
                working=working,
                net_fixed=net_fixed,
                dividend=dividend,
                owner_cash=owner_cash,
                cash=closing,
            )
        )
        carried_cash = closing
        volume_prior = volume

    rates = path["equity_discount_range"]
    growth = path["steady_growth"]
    # 若期末资金有缺口，直接从业务权益价值扣除负债本金，终态利润恢复至增量利息前。
    multiples = [
        (1 + growth) * (1 - growth / roe) / (rate - growth)
        for roe, rate in zip(path["steady_roe"], rates, strict=True)
    ]
    terminal = [(normal_income * multiple + carried_cash) / shares for multiple in multiples]
    dividends = [y["dividend"] / shares for y in years]
    values = [
        present_value(dividends, end, rate) for end, rate in zip(terminal, rates, strict=True)
    ]
    return dict(
        today=values,
        terminal=terminal,
        dividends=dividends,
        multiples=multiples,
        terminal_weight=[
            end / (1 + rate) ** 5 / value
            for end, value, rate in zip(terminal, values, rates, strict=True)
        ],
        years=years,
    )


def main():
    data = json.loads((ROOT / "2026-Q3-input.json").read_text())
    facts = data["facts"]
    revenue = facts["revenue_fy25"] - facts["revenue_9m25"] + facts["revenue_9m26"]
    cost = facts["cost_fy25"] - facts["cost_9m25"] + facts["cost_9m26"]
    gross = revenue - cost
    paths = {k: run_path(facts, p, revenue, gross) for k, p in data["paths"].items()}
    base = paths["base"]
    anchors = {
        k: round(paths[k]["today"][0], 2) for k in ("structural_bear", "cyclical_bear", "bull")
    }
    anchors.update(base_low=round(base["today"][0], 2), base_high=round(base["today"][1], 2))
    assert [
        anchors[k] for k in ("structural_bear", "cyclical_bear", "base_low", "base_high", "bull")
    ] == sorted(anchors.values())
    assert isclose(present_value([1, 1], 10, 0.1), 10, abs_tol=1e-9)
    # 无增长、无需新增资本，利润十元全额分红，期末同样按10%永续资本化。
    flat = dict(
        data["paths"]["base"],
        volume=[1] * 5,
        unit_gross=[1] * 5,
        net_capture=1,
        net_fixed_investment=[0] * 5,
        extra_cash_tied=[0] * 5,
        payout=1,
        steady_growth=0,
        steady_roe=[0.1, 0.1],
        equity_discount_range=[0.1, 0.1],
    )
    assert isclose(run_path({"shares": 1}, flat, 100, 10)["today"][0], 100, abs_tol=1e-9)
    sec = data["book_cross_check"]
    book = facts["common_book"] / facts["shares"]
    check = [
        book * (roe - sec["growth"]) / (sec["discount"] - sec["growth"])
        for roe in sec["sustainable_roe"]
    ]
    result = dict(
        symbol=data["symbol"],
        report_period=data["report_period"],
        value_range=dict(low=anchors["base_low"], high=anchors["base_high"], currency="CNY"),
        return_model=dict(
            schema_version=1,
            method="annual_common_equity_irr_v1",
            currency="CNY",
            model_as_of=data["as_of"],
            base_case_distributions_per_share=[round(x, 4) for x in base["dividends"]],
            base_case_terminal_equity_value_range_per_share={
                "year_5": {
                    "low": round(base["terminal"][0], 2),
                    "high": round(base["terminal"][1], 2),
                }
            },
        ),
        scenarios=dict(
            currency="CNY",
            **anchors,
            horizon_note="按未来五年销量、单位毛利、投资与资金占用分别预算，所有锚点折算到资料截止日。",
        ),
        common_equity_bridge=dict(
            shares_m=facts["shares"],
            parent_book_m=facts["common_book"],
            unpledged_cash_m=round(facts["cash"] - facts["pledged_cash"], 2),
            bank_debt_m=round(sum(facts["bank_debt"]), 2),
            opening_excess_cash_credited=0,
        ),
        ltm=dict(
            revenue_m=round(revenue, 2),
            gross_m=round(gross, 2),
            net_m=round(
                facts["parent_income_fy25"]
                - facts["parent_income_9m25"]
                + facts["parent_income_9m26"],
                2,
            ),
        ),
        historical_ctc_gross_per_t=[
            round(p * 1e6 / v) for p, v in zip(facts["prior_ctc_gross_m"], facts["prior_volume_t"])
        ],
        book_cross_check=[round(v, 2) for v in check],
        paths={},
    )
    for name, p in paths.items():
        ys = p["years"]
        result["paths"][name] = dict(
            year5_income_m=round(ys[-1]["net_income"], 2),
            years1to5_net_capex_m=round(sum(y["net_fixed"] for y in ys), 2),
            years1to5_incremental_working_m=round(sum(y["working"] for y in ys), 2),
            year5_incremental_cash_m=round(ys[-1]["cash"], 2),
            year5_core_pe=[round(x, 2) for x in p["multiples"]],
            terminal_weight_pct=[round(x * 100, 1) for x in p["terminal_weight"]],
            dividends_per_share=[round(x, 4) for x in p["dividends"]],
        )
    (ROOT / "2026-Q3-output.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
