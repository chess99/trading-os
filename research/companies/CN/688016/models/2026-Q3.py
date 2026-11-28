"""心脉医疗。盈利不含财资收益，研发按当期经济成本计，余额为净增固定及营运资本。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PERIOD = "2026-Q3"


def holder_value(dividends, residual, rate):
    return sum(cash / (1 + rate) ** year for year, cash in enumerate(dividends, 1)) + residual / (1 + rate) ** len(dividends)


def evaluate(inputs, case):
    shares = inputs["shares_issued"]  # 库存股按未来全部交付激励且无增资处理
    cash = (inputs["cash_equivalents"] + inputs["liquid_investments"]
            - inputs["dividend_paid_after_quarter"] - inputs["lease_debt"]
            - inputs["minority_interest"] - inputs["operating_cash_floor"]
            - inputs["remaining_base_project_cash"])
    initial_cash = cash
    sales = inputs["trailing_sales"]
    aortic = sales * inputs["aortic_weight"]
    other = sales - aortic
    aortic_factor = (1 + case["aortic_unit_growth"]) * (1 + case["aortic_price_mix"])
    other_factor = (1 + case["peripheral_unit_growth"]) * (1 + case["peripheral_price_mix"])
    dividends = [d * case["dividend_scale"] for d in inputs["dividend_per_share"]]
    rate = case["discount_rate"]
    cap_ratio = case["incremental_capital_per_revenue"]
    fcf_series = []
    capital_series = []
    earnings_series = []
    for year, dps in enumerate(dividends, 1):
        prior_sales = sales
        aortic *= aortic_factor
        other *= other_factor
        sales = aortic + other
        margin = case["margin_year1"] + (case["margin_year5"] - case["margin_year1"]) * (year - 1) / 4
        earnings = sales * margin
        # 下滑期持有存货和设施，不强制释放资本；已有设施折旧与常规维护开支互抵。
        capital = max(sales - prior_sales, 0) * cap_ratio
        if year == 1:
            capital += case["first_year_cash_collection_shortfall"]
        fcf = earnings - capital
        cash += fcf - shares * dps
        assert cash > 0
        capital_series.append(capital)
        earnings_series.append(earnings)
        fcf_series.append(fcf)
    assert isclose(initial_cash + sum(fcf_series), cash + sum(dividends) * shares)
    terminal = (earnings * case["year5_multiple"] + cash) / shares
    value = holder_value(dividends, terminal, rate)
    # 第二方法用显性过渡和永续现金流替代退出倍数，第五年以后的现金流不计入第一方法。
    growth = sales / prior_sales - 1
    terminal_growth = case["terminal_growth"]
    transition_cash = []
    exit_sales = sales
    for step in range(1, 6):
        growth_now = growth + (terminal_growth - growth) * step / 5
        addition = sales * growth_now
        sales += addition
        transition_cash.append(sales * case["margin_year5"] - max(addition, 0) * cap_ratio)
    next_fcf = sales * (1 + terminal_growth) * case["margin_year5"] - sales * terminal_growth * cap_ratio
    continuing = next_fcf / (rate - terminal_growth)
    dcf_terminal = (cash + holder_value(transition_cash, continuing, rate)) / shares
    return {
        "value": round(value, 2), "year5_total_per_share": round(terminal, 2),
        "year5_sales_mn": round(exit_sales, 1), "year5_earnings_mn": round(earnings, 1),
        "retained_cash_year5_mn": round(cash, 1), "opening_surplus_mn": round(initial_cash, 1),
        "terminal_share": round(terminal / (1 + rate) ** 5 / value, 3),
        "dcf_per_share": round(holder_value(dividends, dcf_terminal, rate), 2),
        "capital_from_year1_end_to_year5_end_mn": round(sum(capital_series[1:]), 1),
        "earnings_increase_from_year1_to_year5_mn": round(earnings_series[-1] - earnings_series[0], 1)
    }


def main():
    assert isclose(holder_value([1, 1], 10, 0.1), 10)  # 每期付息1，第2年还本10。
    inputs = json.loads((ROOT / f"{PERIOD}-input.json").read_text())
    details = {name: evaluate(inputs, dict(zip(inputs["case_fields"], values, strict=True)))
               for name, values in inputs["cases"].items()}
    values = {k: v["value"] for k, v in details.items()}
    assert list(values.values()) == sorted(values.values())
    interval = {"low": values["base_low"], "high": values["base_high"], "currency": "CNY"}
    terminal = {edge: details["base_" + edge]["year5_total_per_share"] for edge in ["low", "high"]}
    model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY",
             "model_as_of": inputs["as_of"], "base_case_distributions_per_share": inputs["dividend_per_share"],
             "base_case_terminal_equity_value_range_per_share": {"year_5": terminal}}
    result = {"symbol": "CN:688016", "report_period": PERIOD, "value_range": interval, "return_model": model,
              "scenarios": {"currency": "CNY", **values, "horizon_note": "五年销量与价格组合决定税后经营利润，扣新增资本、回款缺口与分红后，将第五年业务和留存现金折现。"},
              "details": details}
    (ROOT / f"{PERIOD}-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
