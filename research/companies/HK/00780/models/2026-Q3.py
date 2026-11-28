"""同程旅行 2026-Q3。运行本文件，在同目录生成简明结果。依赖 Python 标准库。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def discounted_equity(dividends, terminal, rate):
    horizon = len(dividends)
    pv_dividends = sum(cash / (1 + rate) ** year for year, cash in enumerate(dividends, 1))
    pv_terminal = terminal / (1 + rate) ** horizon
    return pv_dividends + pv_terminal, pv_terminal


def opening_common_assets(balance):
    cash = balance["cash"] + balance["short_deposits"] + balance["short_fv"] * balance["short_fv_recovery"]
    investments = (balance["long_fv"] + balance["associates"] + balance["long_deposits"]) * balance["long_recovery"]
    return cash + investments - balance["bank_loans"] - balance["financial_claim"] - balance["minority"] - balance["reserve"]


def scenario(revenue, shares, opening_assets, capital, path):
    fx = capital["cny_per_hkd"]
    unit = shares * fx
    cash = opening_assets
    rate, growth = path["rate"], path["g"]
    for change, margin, dividend in zip(path["growth"], path["margin"], path["dividends"]):
        next_revenue = revenue * (1 + change)
        expansion = max(0, next_revenue - revenue) / path["sales_to_capital"]
        profit = next_revenue * margin * (1 - capital["tax"])
        deal_cost = next_revenue * path["ongoing_deals"]
        free_cash = profit - expansion - deal_cost
        opening = cash
        dividend_total = dividend * unit
        cash = opening * (1 + capital["cash_yield_after_tax"]) + free_cash - dividend_total
        assert cash >= 0 and abs(cash + dividend_total - opening * (1 + capital["cash_yield_after_tax"]) - free_cash) < 1e-8
        revenue = next_revenue
    net_cash_yield = profit * (1 + growth) * (1 - growth / path["terminal_roic"]) - deal_cost * (1 + growth)
    operating_value = net_cash_yield / (rate - growth)
    terminal = (operating_value + cash) / unit
    value, pv_terminal = discounted_equity(path["dividends"], terminal, rate)
    # 交叉检验单独资本化可持续税后经营盈利；同一经营外资产和已派股息。
    multiple_terminal = ((profit - deal_cost) * path["multiple"] + cash) / unit
    secondary, _ = discounted_equity(path["dividends"], multiple_terminal, rate)
    return {"value":round(value,2),"terminal":round(terminal,2),"terminal_pv_weight":round(pv_terminal/value,4),
            "method_two":round(secondary,2),"sales_y5":round(revenue,3),"after_tax_op_y5":round(profit,3),
            "retained_assets_y5":round(cash,3)}


def main():
    assert abs(discounted_equity([1], 10, .10)[0] - 10) < 1e-12
    data = json.loads((ROOT / "2026-Q3-input.json").read_text())
    r, cap = data["revenue"], data["capital"]
    ltm = r["fy25"] - r["h125"] - r["q325"] + r["h126"] + r["q326"]
    shares = cap["issued"] + sum(cap["options_million"]) / 1000
    opening = opening_common_assets(data["balance"])
    cases = {name:scenario(ltm, shares, opening, cap, path) for name, path in data["paths"].items()}
    names = ["structural_bear","cyclical_bear","base_low","base_high","bull"]
    anchors = {name:cases[name]["value"] for name in names}
    assert list(anchors.values()) == sorted(anchors.values())
    assert data["paths"]["base_low"]["dividends"] == data["paths"]["base_high"]["dividends"]
    model = {"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"HKD","model_as_of":data["cutoff"],
             "base_case_distributions_per_share":data["paths"]["base_low"]["dividends"],
             "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":cases["base_low"]["terminal"],"high":cases["base_high"]["terminal"]}}}
    sensitivity = {}
    for name, change in {"margin_down_1ppt":{"margin":[m - .01 for m in data["paths"]["base_low"]["margin"]]},
                          "rate_up_1ppt":{"rate":data["paths"]["base_low"]["rate"]+.01}}.items():
        sensitivity[name] = scenario(ltm, shares, opening, cap, dict(data["paths"]["base_low"], **change))["value"]
    result = {"symbol":data["symbol"],"report_period":data["report_period"],"value_range":{"low":anchors["base_low"],"high":anchors["base_high"],"currency":"HKD"},
              "return_model":model,"scenarios":{"currency":"HKD",**anchors},"opening_common_assets_cny_bn":round(opening,3),
              "ltm_revenue_cny_bn":round(ltm,3),"diluted_shares_bn":round(shares,6),"cases":cases,"base_low_sensitivity_hkd":sensitivity}
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")


if __name__ == "__main__":
    main()
