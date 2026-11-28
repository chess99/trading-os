"""运行 python3 2026-Q3.py，在脚本同目录生成摘要。金额单位十亿元人民币。"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "2026-Q3-input.json").read_text())
cash = data["cash_bridge"]
shares = data["share_bridge"]
fx = data["cny_per_hkd"]
share_count = (shares["class_a"] + shares["class_b_ex_treasury"] - shares["repurchased_pending_cancel"]
               + shares["q3_dilutive_options_rsu_proxy"] + shares["november_parent_awards"])
opening_surplus = (cash["reported_cash_resources"] - cash["restricted"] - cash["borrowing_including_convertible"]
                   + (cash["common_and_preferred_investments"] + cash["equity_method_investments"])
                   * cash["investment_realization_fraction"] - cash["outside_fund_claim_estimate"]
                   - cash["noncontrolling_interest"] - cash["deferred_asset_purchase_estimate"]
                   - cash["operating_cash_required"] - cash["post_quarter_buybacks_hkd"] * fx)


def present(terminal_operations, retained_cash, discount, years, shares_out, cny_hkd):
    return (terminal_operations + retained_cash) / ((1 + discount) ** years * shares_out * cny_hkd)


def run_case(parameters):
    rate = parameters["discount"]
    stable = parameters["steady_growth"]
    growth6 = parameters["year6_growth"]
    roic = parameters["incremental_roic"]
    balance = opening_surplus
    last_sales = None
    rows = []
    for year in range(1, 6):
        t = (year - 1) / 4
        def interpolate(name):
            first, last = parameters[name]
            return first + (last - first) * t
        core = interpolate("core_revenue")
        new = interpolate("deliveries") * interpolate("vehicle_asp") * (1 + parameters["related_sales_ratio"])
        sales = core + new
        ebit = core * interpolate("core_margin") + new * interpolate("new_business_margin")
        tax = max(ebit, 0) * data["tax"]
        earnings = (ebit - tax) * (1 - data["subsidiary_awards_profit_haircut"])
        working_capital = (parameters["first_working_capital"] if last_sales is None else
                           (sales - last_sales) * parameters["incremental_working_capital_rate"])
        net_capex = interpolate("net_capex")
        retained = earnings - net_capex - working_capital
        balance += retained
        rows.append((earnings, net_capex, working_capital, retained))
        last_sales = sales
    assert min(opening_surplus + sum(r[-1] for r in rows[:end]) for end in range(1, 6)) >= 0
    assert abs(balance - opening_surplus - sum(r[-1] for r in rows)) < 1e-8
    operation = earnings * parameters["earnings_multiple"]
    value = present(operation, balance, rate, 5, share_count, fx)
    terminal = present(operation, balance, rate, 0, share_count, fx)
    # 次法独立推算经营业务在Y5末的价值。增长所需增量资本在相同年度扣除。
    future_profit = earnings
    dcf = 0.0
    for step in range(1, 6):
        growth = growth6 + (stable - growth6) * (step - 1) / 4
        incremental_profit = future_profit * growth
        future_profit += incremental_profit
        dcf += (future_profit - incremental_profit / roic) / (1 + rate) ** step
    steady_fcfe = future_profit * (1 + stable) - future_profit * stable / roic
    dcf += steady_fcfe / (rate - stable) / (1 + rate) ** 5
    return dict(today=round(value, 2), year5=round(terminal, 2),
                dcf=round(present(dcf, balance, rate, 5, share_count, fx), 2),
                y1_after_tax=round(rows[0][0], 2), y5_after_tax=round(earnings, 2),
                retained_cash_y5=round(balance, 2), y5_fcf=round(rows[-1][-1], 2),
                incremental_capital_y1_to_y5=round(sum(r[1]+r[2] for r in rows[1:]), 2),
                y5_operating_fraction=round(operation / (operation + balance), 4))


assert abs(present(100, 10, .1, 1, 5, 1) - 20) < 1e-10
cases = {name: run_case(params) for name, params in data["cases"].items()}
values = [r["today"] for r in cases.values()]
assert values == sorted(values) and min(values) >= 0
low, high = cases["base_low"], cases["base_high"]
result = dict(symbol=data["symbol"], report_period=data["report_period"],
              value_range=dict(low=low["today"], high=high["today"], currency="HKD"),
              return_model=dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD",
                                model_as_of=data["as_of"], base_case_distributions_per_share=[0.0]*5,
                                base_case_terminal_equity_value_range_per_share={
                                    "year_5": dict(low=low["year5"], high=high["year5"])}),
              diluted_shares_billion=round(share_count, 5), opening_surplus_rmb_billion=round(opening_surplus, 3),
              cases=cases)
(HERE / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
