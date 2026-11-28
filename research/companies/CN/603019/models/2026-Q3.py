"""运行本文件，从同目录读取三季报输入并生成估值结果。"""
from pathlib import Path
import json
import math


def convertible_equity(gross_equity, par, redemption, conversion_price, shares):
    """末期债权人有权选择现金或普通股；观察同一普通股在两种结算方式下的归属。"""
    diluted = shares + par / conversion_price
    return max(0.0, min((gross_equity - redemption) / shares, gross_equity / diluted))


def continuing_value(profit, growth, returns, discount, steady_growth, steady_returns):
    """在Y5时点估算Y6—10资本投入后的收益及Y10以后价值。"""
    total = 0
    for year in range(1, 6):
        step = (year - 1) / 4
        annual_growth = growth * (1 - step) + steady_growth * step
        annual_returns = returns * (1 - step) + steady_returns * step
        reinvestment = profit * annual_growth / annual_returns
        profit *= 1 + annual_growth
        total += (profit - reinvestment) / (1 + discount) ** year
    steady_cash = profit * (1 + steady_growth) - profit * steady_growth / steady_returns
    return total + steady_cash / (discount - steady_growth) / (1 + discount) ** 5


def scenario(data, assumptions):
    b = data["bridge"]
    s = assumptions
    shares = b["shares"]
    starting_cash = b["cash"] - sum(b[k] for k in (
        "short_loans", "current_debt", "long_loans", "leases", "minority_claim",
        "earmarked_project_float", "operating_liquidity", "employee_buyback_budget", "equity_commitments"
    ))
    cash = starting_cash
    previous_sales = data["opening_sales_estimate"]
    payout_pv = cumulative_cash = cumulative_dividends = 0.0
    capital = operating_profit_y1 = first_year_capital = 0.0
    for index in range(5):
        weight = index / 4
        sales = s["sales_1"] * (s["sales_5"] / s["sales_1"]) ** weight
        margin = s["margin_1"] * (1 - weight) + s["margin_5"] * weight
        operating_profit = sales * margin
        affiliate = b["hygon_stake"] * s["hygon_profit_1"] * (s["hygon_profit_5"] / s["hygon_profit_1"]) ** weight
        project = (s["project_pay"] * data["project_pay_weights"][index]
                   - s["project_da"] * data["cumulative_project_amortization_offset_weights"][index])
        # 销售下行时，不假设原有备货及安装工程能随需求下降立即释放资金。
        added_working_cash = max(0.0, sales - previous_sales) * s["wc_ratio"]
        capital += project + added_working_cash
        if index == 0:
            first_year_capital = capital
            operating_profit_y1 = operating_profit
        cash_earned = operating_profit - project - added_working_cash + affiliate * s["affiliate_payout"] - b["coupons"][index]
        dividend = s["dividend_scale"] * data["base_dividends_per_share"][index]
        cash += cash_earned - dividend * shares
        assert cash >= 0, "未来支付需要另计过桥融资"
        cumulative_cash += cash_earned
        cumulative_dividends += dividend * shares
        payout_pv += dividend / (1 + s["discount"]) ** (index + 1)
        previous_sales = sales
    assert math.isclose(starting_cash + cumulative_cash, cash + cumulative_dividends)
    other_holdings = b["other_associates_h1_book"] * s["other_book_recovery"]
    gross = other_holdings + operating_profit * s["op_multiple"] + affiliate * s["affiliate_multiple"] + cash
    def equity_at_five(total):
        return convertible_equity(total, b["par"], b["redemption"], b["conversion_price"], shares)
    terminal = equity_at_five(gross)
    end_pv = terminal / (1 + s["discount"]) ** 5
    aux = data["secondary"]
    op_dcf = continuing_value(operating_profit, aux["transition_operating_growth"], aux["transition_operating_roic"],
                              s["discount"], aux["steady_growth"], aux["operating_steady_roic"])
    affiliate_dcf = continuing_value(affiliate, aux["transition_hygon_growth"], aux["transition_hygon_roe"],
                                     s["discount"], aux["steady_growth"], aux["hygon_steady_roe"])
    return {
        "present_per_share": round(payout_pv + end_pv, 2), "year5_per_share": round(terminal, 2),
        "dcf_check": round(payout_pv + equity_at_five(op_dcf + affiliate_dcf + other_holdings + cash) / (1 + s["discount"]) ** 5, 2),
        "terminal_pv_fraction": round(end_pv / (end_pv + payout_pv), 4), "opening_cash_bridge": round(starting_cash, 2),
        "year5_cash_before_bond": round(cash, 2), "operating_profit_year5": round(operating_profit, 2),
        "affiliate_attributable_year5": round(affiliate, 2), "net_growth_capital_y1_to_y5": round(capital - first_year_capital, 2),
        "incremental_op_profit_y1_to_y5": round(operating_profit - operating_profit_y1, 2),
        "no_conversion_terminal": round((gross - b["redemption"]) / shares, 2),
        "full_conversion_terminal": round(gross / (shares + b["par"] / b["conversion_price"]), 2)
    }


def main():
    root = Path(__file__).resolve().parent
    data = json.loads((root / "2026-Q3-input.json").read_text())
    assert convertible_equity(120, 20, 20, 10, 10) == 10
    assert convertible_equity(240, 20, 20, 10, 10) == 20
    assert math.isclose(continuing_value(10, 0, 0.2, 0.1, 0, 0.2), 100)
    for k in ("project_pay_weights", "cumulative_project_amortization_offset_weights"):
        assert math.isclose(sum(data[k]), 1)
    assert math.isclose(data["scenarios"]["base_low"]["project_pay"], data["project_capital_and_initial_working_cash"])
    detail = {name: scenario(data, s) for name, s in data["scenarios"].items()}
    anchors = {name: row["present_per_share"] for name, row in detail.items()}
    assert list(anchors.values()) == sorted(anchors.values())
    core = {"low": anchors["base_low"], "high": anchors["base_high"], "currency": "CNY"}
    terminal = {edge: detail["base_" + edge]["year5_per_share"] for edge in ("low", "high")}
    result = {
        "symbol": data["symbol"], "report_period": data["report_period"], "value_range": core,
        "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY",
                         "model_as_of": data["as_of"], "base_case_distributions_per_share": data["base_dividends_per_share"],
                         "base_case_terminal_equity_value_range_per_share": {"year_5": terminal}},
        "scenarios": anchors, "paths": detail,
    }
    (root / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
