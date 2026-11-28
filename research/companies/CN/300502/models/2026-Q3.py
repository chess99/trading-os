"""在本目录用 Python 运行本文件，根据同目录输入重建结果。"""
import json
from pathlib import Path
from math import isclose


def annual_cash(open_capital, close_capital, after_tax_profit, common):
    return (after_tax_profit - (close_capital - open_capital)) * common


def path_value(b, p, multiple, crosscheck=None):
    shares = b["issued_shares"] - b["treasury_shares"] + b["old_unvested_shares"] + b["new_award_and_reserve"]
    wc = (b["ar_and_bills"] + b["inventory"] * (1 - p["inventory_loss"])
          + b["prepaid_material"] + b["other_current_assets"] - b["ap_and_bills"] - b["contract_liabilities"])
    fixed = b["plant"] + b["construction"] + b["equipment_and_material_advances"]
    opening_cash = (b["cash_equivalents"] - b["buyback_paid"] - b["unspent_buyback_budget"]
                    - b["lease_debt"] - b["deferred_employee_liability"] - b["operating_cash_floor"]) * b["common_share"]
    capital, cash = wc + fixed, opening_cash
    payments, profits, capitals, flows = [], [], [], []
    for volume, price, margin in zip(p["volume"], p["asp"], p["margin"], strict=True):
        revenue = volume * price / 1000
        profit = revenue * margin
        fixed = max(fixed, revenue * p["fixed_ratio"])
        new_capital = fixed + revenue * p["wc_ratio"]
        flow = annual_cash(capital, new_capital, profit, b["common_share"])
        cash += flow
        assert cash >= 0, "现金预算不足，需另行建模外部融资"
        pay = min(cash, max(profit * b["common_share"] * p["payout"], 0))
        cash -= pay
        payments.append(pay)
        flows.append(flow)
        capitals.append(new_capital)
        profits.append(profit * b["common_share"])
        capital = new_capital
    assert isclose(cash + sum(payments), opening_cash + sum(flows), abs_tol=1e-8)
    rate = p["rate"]
    operating_exit = profits[-1] * multiple
    if crosscheck:
        operating_exit = 0
        last_margin = p["margin"][-1]
        for n, growth in enumerate(crosscheck["growth_years_6_to_10"], 1):
            revenue *= 1 + growth
            margin = last_margin + (crosscheck["margin_year_10"] - last_margin) * n / 5
            profit = revenue * margin
            new_capital = revenue * (p["fixed_ratio"] + p["wc_ratio"])
            flow = annual_cash(capital, new_capital, profit, b["common_share"])
            operating_exit += flow / (1 + rate) ** n
            capital = new_capital
        growth = crosscheck["steady_growth"]
        terminal_flow = profit * b["common_share"] * (1 + growth) * (1 - growth / crosscheck["steady_return_on_new_capital"])
        operating_exit += terminal_flow / (rate - growth) / (1 + rate) ** 5
    terminal = (cash + operating_exit) / shares
    discounted_terminal = terminal / (1 + rate) ** 5
    value = discounted_terminal + sum(pay / shares / (1 + rate) ** year for year, pay in enumerate(payments, 1))
    return {"present_value":round(value, 2), "terminal_value":round(terminal, 2),
            "distributions":[round(pay / shares, 4) for pay in payments],
            "terminal_pv_fraction":round(discounted_terminal / value, 3),
            "shares_bn":round(shares, 9), "opening_surplus_bn":round(opening_cash, 3),
            "year_5_retained_cash_bn":round(cash, 3),
            "y1_y5_incremental_after_tax_operating_return":round((profits[-1] - profits[0]) / (capitals[-1] - capitals[0]) / b["common_share"], 3)
            if capitals[-1] > capitals[0] else None}


def build(j):
    b, paths = j["basis"], j["paths"]
    # 用相同函数验证无增长、无折现、每年全额分配且末年一倍盈利的手算例。
    simple_basis = {k:0 for k in b} | {"issued_shares":1,"common_share":1}
    simple_path = {"volume":[1]*5,"asp":[1000]*5,"margin":[1]*5,"wc_ratio":0,"fixed_ratio":0,
                   "inventory_loss":0,"payout":1,"rate":0}
    assert path_value(simple_basis, simple_path, 1)["present_value"] == 6
    rows = {key:path_value(b, p, p["multiple"]) for key, p in paths.items() if key != "base"}
    base = paths["base"]
    for key, multiple in zip(("base_low","base_high"), base["multiple"], strict=True):
        rows[key] = path_value(b, base, multiple)
    order = ["structural_bear","cyclical_bear","base_low","base_high","bull"]
    anchors = {k:rows[k]["present_value"] for k in order}
    assert list(anchors.values()) == sorted(anchors.values())
    lo, hi = rows["base_low"], rows["base_high"]
    assert lo["distributions"] == hi["distributions"]
    return {"symbol":j["symbol"],"report_period":j["report_period"],
            "value_range":{"low":lo["present_value"],"high":hi["present_value"],"currency":"CNY"},
            "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"CNY","model_as_of":j["as_of"],
                            "base_case_distributions_per_share":lo["distributions"],
                            "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":lo["terminal_value"],"high":hi["terminal_value"]}}},
            "scenarios":{"currency":"CNY",**anchors,"horizon_note":"按统一完全稀释股数，联动销量、产品组合、资本占用、减值及分配，折现五年分配和独立第五年末普通股价值。"},
            "path_details":rows,"cashflow_crosscheck":path_value(b,base,0,j["cashflow_check"]),
            "margin_sensitivity":path_value(b,base | {"margin":base["margin"][:-1]+[base["margin"][-1]-.03]},sum(base["multiple"])/2)["present_value"]}


if __name__ == "__main__":
    folder = Path(__file__).resolve().parent
    inputs = json.loads((folder / "2026-Q3-input.json").read_text())
    (folder / "2026-Q3-output.json").write_text(json.dumps(build(inputs),ensure_ascii=False,indent=2)+"\n")
