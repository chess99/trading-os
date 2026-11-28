"""华峰测控普通股估值。金额为百万元，股份为百万股。"""
from pathlib import Path
import json
import math

root = Path(__file__).resolve().parent
data = json.loads((root / "2026-Q3-input.json").read_text())
opening = data["opening"]


def present(cashflows, terminal, rate):
    periods = len(cashflows)
    return sum(flow / (1 + rate) ** year for year, flow in enumerate(cashflows, 1)) + terminal / (1 + rate) ** periods


def model(path):
    p = dict(zip(data["parameter_names"], path, strict=True))
    o = opening
    shares = o["registered_shares"] + o["award_dilution_budget"]
    gross_lx = o["lx_shares_before_capitalization"] * (1 + o["lx_stock_distribution"]) * o["lx_close_on_cutoff"] * p["lx_realizable"]
    net_lx = gross_lx - max(gross_lx - o["lx_tax_basis"], 0) * o["disposal_tax_rate"]
    other_assets = (o["other_equities_h1"] + o["funds_q3"] + o["equity_method_q3"]) * p["other_investment_realizable"]
    debt = o["bond_face"] * (o["bond_maturity_multiple"] + sum(o["other_coupon_rates"]))
    initial_capital = (o["cash"] + o["liquid_investments"] - o["operating_cash_reserve"] -
                       o["buyback_budget_including_paid"] - o["lease_and_current_debt"] -
                       o["minority"] - debt + net_lx + other_assets)
    # 仅现金及其投资收益留存滚动，未变现的战略持仓以税后可实现额平移。
    retained = initial_capital - other_assets - net_lx
    y5_sales = p["systems_y5"] * p["system_asp_y5"] * (1 + p["other_sales_to_systems"])
    last_sales = o["opening_sales_estimate"]
    dividends, annual = [], []
    for year, budget in enumerate(o["scheduled_dividends_per_share"], 1):
        progress = (year - 1) / 4
        sales = p["first_year_sales"] * (y5_sales / p["first_year_sales"]) ** progress
        margin = p["margin_y1"] + (p["margin_y5"] - p["margin_y1"]) * progress
        earnings = sales * margin
        fixed = sales * p["capital_expenditure_net_to_sales"]
        # 不预设销售回落即可按原价收回旧库存及应收款。
        working = max(0, sales - last_sales) * p["working_capital_to_growth"]
        free = earnings - fixed - working
        dividend = min(budget * shares, max(0, free))
        before = retained
        retained = before * (1 + o["cash_yield"]) + free - dividend
        assert retained > 0 and math.isclose(retained + dividend, before * (1 + o["cash_yield"]) + free)
        annual.append(dict(revenue=sales, operating_net_income=earnings, net_capex=fixed, working_capital_added=working, free=free))
        dividends.append(dividend / shares)
        last_sales = sales
    capital_y5 = retained + other_assets + net_lx
    terminal = (capital_y5 + earnings * p["terminal_operating_pe"]) / shares
    rate = p["discount"]
    core = present(dividends, terminal, rate)
    # 方法二以第6至10年现金与稳态再投资推导第5年业务价值。
    later = []
    g = p["perpetual_growth"]
    for step in range(5):
        growth = p["transition_growth_y6"] + (g - p["transition_growth_y6"]) * step / 4
        next_sales = last_sales * (1 + growth)
        later.append(next_sales * p["margin_y5"] - next_sales * p["capital_expenditure_net_to_sales"] -
                     (next_sales - last_sales) * p["working_capital_to_growth"])
        last_sales = next_sales
    steady = last_sales * (1 + g) * p["margin_y5"] * (1 - g / p["steady_roic"]) / (rate - g)
    alt = present(dividends, (capital_y5 + present(later, steady, rate)) / shares, rate)
    return dict(value=round(core, 2), alternative=round(alt, 2), terminal=round(terminal, 2),
                terminal_share=round(terminal / (1 + rate) ** 5 / core, 4),
                distributions=[round(x, 3) for x in dividends], annual=annual, net_lx=net_lx,
                opening_bridge=initial_capital, terminal_capital=capital_y5, bond_cash_reserved=debt, shares=shares)


assert present([1, 1], 8, 0) == 10
assert math.isclose(present([2], 20, 0.1), 20)
paths = {key: model(values) for key, values in data["paths"].items()}
anchors = {key: row["value"] for key, row in paths.items()}
assert list(anchors.values()) == sorted(anchors.values())
low, high = paths["base_low"], paths["base_high"]
assert low["distributions"] == high["distributions"]
result = dict(symbol=data["symbol"], report_period=data["report_period"],
              value_range=dict(low=low["value"], high=high["value"], currency="CNY"),
              scenarios=dict(currency="CNY", **anchors, horizon_note="五年末系统销量、组合均价、经营净利率与必要再投资联动，战略持股按税后可实现额独立计入。"),
              return_model=dict(schema_version=1, method="annual_common_equity_irr_v1", currency="CNY",
                                model_as_of=data["as_of"], base_case_distributions_per_share=low["distributions"],
                                base_case_terminal_equity_value_range_per_share={"year_5": dict(low=low["terminal"], high=high["terminal"])}),
              paths=paths)
(root / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
