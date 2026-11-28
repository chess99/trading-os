"""用 Python 3 运行本文件，在输入旁生成简明估值。金额单位为人民币亿元。"""
import json
from pathlib import Path
from math import isclose

ROOT = Path(__file__).resolve().parent
DATE = "2026-11-27T18:05:00+08:00"


def annual(revenue, growth, margin, floor, path, depreciation_rate):
    """已费用化研发、利息及少数权益均在归母净利率中，维护开支按折旧估算。"""
    change = revenue * growth
    revenue += change
    profit = revenue * margin
    fixed = max(floor, max(change, 0) * path["fixed_per_sales_increment"])
    upkeep = revenue * path["extra_upkeep_sales"]
    # 订单下滑时不假设存货与应收可以立即变现。
    working = max(change, 0) * path["working_per_sales_increment"]
    depreciation = revenue * depreciation_rate
    capex = depreciation + upkeep + fixed
    free_cash = profit + depreciation - capex - working
    return revenue, profit, free_cash, fixed + working, capex


def value(inputs, path, rate):
    facts, assumptions = inputs["facts"], inputs["assumptions"]
    shares = facts["issued_shares"] + facts["reserve_grants"]
    revenue = facts["sales_9m"] + facts["sales_2025q4"] * (1 + facts["q4_growth_estimate"])
    reserve = facts["parent_retained_h1"]
    # 经营现金和融资一并留在业务中。认购款留作限制性股票对应的履约准备。
    cash = 0
    book = facts["book_equity_q3"]  # 限制性股票发行及对应回购义务的净权益影响取零
    distributions, book_series, profits, reinvestments, cashflows, capex_series = [], [book], [], [], [], []
    assert len(path["growth"]) == len(path["margin"]) == len(assumptions["project_spend_floor"]) == 5
    for growth, margin, floor in zip(path["growth"], path["margin"], assumptions["project_spend_floor"]):
        revenue, profit, free_cash, invest, capex = annual(revenue, growth, margin, floor, path, assumptions["depreciation_to_sales"])
        reserve += profit * path["parent_profit_ratio"] * (1 - assumptions["parent_reserve"])
        cash += free_cash
        dividend = min(profit * path["target_payout"], reserve, cash)
        assert dividend >= 0
        reserve -= dividend
        cash -= dividend
        book += profit - dividend
        book_series.append(book)
        profits.append(profit)
        reinvestments.append(invest)
        cashflows.append(free_cash)
        capex_series.append(capex)
        distributions.append(dividend)
    assert isclose(sum(cashflows), sum(distributions) + cash, abs_tol=1e-9)
    assert isclose(book, book_series[0] + sum(profits) - sum(distributions))
    g = path["mature_growth"]
    _, mature_profit, mature_cash, _, _ = annual(revenue, g, path["margin"][-1], 0, path, assumptions["depreciation_to_sales"])
    assert rate > g
    # 终态将再投资后的持续权益现金资本化；积累的未派现金另计一次。
    # 单体常规承接的资金按期支付；其余成熟现金随子公司调度、汇回后支付。
    timely = min(mature_cash, mature_profit * path["parent_profit_ratio"] * (1-assumptions["parent_reserve"]))
    delay_factor = (1 + rate) ** -path["remittance_lag"]
    feasible_cash = timely + (mature_cash - timely) * delay_factor
    accessible = min(cash, reserve)
    terminal = feasible_cash / (rate - g) + accessible + (cash-accessible) * delay_factor
    terminal_pv = terminal / (1 + rate)**5
    pv = sum(d / (1 + rate)**t for t, d in enumerate(distributions, 1)) + terminal_pv
    residual = sum((p - rate * b) / (1 + rate)**t for t, (p, b) in enumerate(zip(profits, book_series), 1))
    residual_values = [(book_series[0] + residual + (roe-rate)*book / (rate-g)/(1+rate)**5)/shares
                       for roe in assumptions["terminal_roe_crosscheck_bounds"]]
    return dict(value=pv/shares, dividends=[d/shares for d in distributions], terminal=terminal/shares,
                terminal_pv_share=terminal_pv/pv, residual_values=residual_values, profit=profits,
                capex=capex_series, reinvestments=reinvestments, retained_cash=cash,
                free_cash=cashflows, legal_reserve=reserve)


def build(inputs):
    paths, f = inputs["paths"], inputs["facts"]
    rates = inputs["assumptions"]["base_rate_bounds"]
    low = value(inputs, paths["base"], max(rates))
    high = value(inputs, paths["base"], min(rates))
    central = value(inputs, paths["base"], paths["base"]["rate"])
    runs = {name: value(inputs, path, path["rate"]) for name, path in paths.items()}
    anchors = {k: round(v["value"], 2) for k, v in runs.items() if k != "base"}
    anchors.update(base_low=round(low["value"], 2), base_high=round(high["value"], 2))
    order = ["structural_bear", "cyclical_bear", "base_low", "base_high", "bull"]
    assert 0 <= anchors[order[0]] and sorted(anchors[k] for k in order) == [anchors[k] for k in order]
    return dict(symbol="CN:002003", report_period="2026-Q3", value_range=dict(currency="CNY",low=anchors["base_low"],high=anchors["base_high"]),
                return_model=dict(schema_version=1,method="annual_common_equity_irr_v1",currency="CNY",model_as_of=DATE,
                  base_case_distributions_per_share=[round(d,4) for d in central["dividends"]],
                  base_case_terminal_equity_value_range_per_share=dict(year_5=dict(low=round(low["terminal"],2),high=round(high["terminal"],2)))),
                scenarios=anchors, diluted_shares=f["issued_shares"]+f["reserve_grants"],
                evidence=dict(residual_crosscheck=central["residual_values"], base=central,
                              opening_liquidity_after_debt_proxy=f["cash_q3"]-f["short_debt_q3"]-f["current_maturities_q3"]-f["lease_debt_q3"]-f["restricted_cash_h1"]))


if __name__ == "__main__":
    data = json.loads((ROOT / "2026-Q3-input.json").read_text())
    # 恒定收入100、利润10、无增量投入、全分配；折现率10%时每股永久价值100。
    from copy import deepcopy
    test = deepcopy(data)
    test["facts"].update(sales_9m=100, sales_2025q4=0, issued_shares=1,reserve_grants=0)
    test["assumptions"].update(project_spend_floor=[0]*5, parent_reserve=0)
    flat = dict(test["paths"]["base"], growth=[0]*5, margin=[0.1]*5, target_payout=1,
                parent_profit_ratio=1, mature_growth=0)
    assert isclose(value(test, flat, 0.1)["value"], 100)
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(build(data), ensure_ascii=False, indent=2)+"\n")
