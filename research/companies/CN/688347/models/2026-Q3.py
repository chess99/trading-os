"""运行 python 2026-Q3.py 读取同目录输入，生成四情景及五年持有人模型。"""
import json
from math import isclose
from pathlib import Path

DIR = Path(__file__).resolve().parent
data = json.loads((DIR / "2026-Q3-input.json").read_text())
f, c = data["facts"], data["common"]
stocks = f["shares_a"] + f["shares_hk"] + f["placement_shares"] + f["old_options"]
shares_bn = stocks / 1e9


def terminal_multiple(growth, reinvestment_roe, discount):
    assert 0 <= growth < min(reinvestment_roe, discount)
    return (1 + growth) * (1 - growth / reinvestment_roe) / (discount - growth)


def roll(s):
    cash = f["cash"] + f["cash_after_placement"]
    debt = f["bank_and_current_debt"] + f["lease"] + f["existing_puttable_payable"]
    book = f["parent_equity"] + f["cash_after_placement"] - f["estimated_disposal_loss_parent"]
    prev_sales = f["q3_annualized_sales"]
    years = []
    for i in range(5):
        blend = i / 4
        capacity = c["year_1_average_capacity"] * (1-blend) + s["capacity"] * blend
        sales = capacity * 12 * s["load"] * s["unit_revenue"] / 1e6
        gross = c["year_1_gross_margin"] * (1-blend) + s["gross_margin"] * blend
        ebit = sales * (gross - s["opex"])
        interest = debt * s["loan_rate"] - min(cash, c["cash_floor"]) * c["cash_rate"]
        pretax = ebit - interest
        profit = pretax - max(0, pretax) * c["income_tax"]
        wuxi_margin = c["year_1_wuxi_net_margin"] * (1-blend) + s["wuxi_net_margin"] * blend
        minority = f["wuxi_nci_share"] * sales * c["wuxi_revenue_fraction"] * wuxi_margin
        parent = profit - minority
        book += parent
        wc = (sales - prev_sales) * c["working_capital_fraction_sales"]
        cash_flow = profit + s["da"][i] - wc - s["capex"][i]
        borrowing = max(0, c["cash_floor"] - cash - cash_flow)
        cash += cash_flow + borrowing
        debt += borrowing
        years.append(dict(sales=sales, ebit=ebit, parent=parent, nci=minority, group_fcf=cash_flow,
                          cash=cash, debt=debt, book=book))
        assert isclose(profit, parent+minority)
        prev_sales = sales
    multiple = terminal_multiple(s["growth"], s["terminal_roe"], s["discount"])
    investment_value = f["strategic_investments"] * (1-c["tax_haircut_financial_assets"]) * c["strategic_asset_realisable"]
    excess = max(0, cash - c["cash_floor"]) * c["parent_excess_cash_share"]
    redemption_loss = f["new_jv_cdb_usd_bn"] * f["budget_usd_cny"] * s["put_loss_fraction"]
    terminal_equity = max(0, parent * multiple + investment_value + excess - redemption_loss)
    per_share = terminal_equity / shares_bn
    # 新授期权在所有年五终值下均处价外；老期权全额保守计入，不计微量对价。
    assert per_share < f["strike_hkd"] * f["hkd_cny"]
    present = per_share / (1+s["discount"])**5
    # 独立交叉检验：估计规划期后整体账面资本可持续回报，并按剩余收益估值。
    secondary = (book * (s["secondary_roe"]-s["growth"]) / (s["discount"]-s["growth"])
                 - redemption_loss) / shares_bn / (1+s["discount"])**5
    incremental_capital = sum(s["capex"][1:])-sum(s["da"][1:]) + (sales-years[0]["sales"])*c["working_capital_fraction_sales"]
    inc_return = (ebit-years[0]["ebit"]) * (1-c["income_tax"]) / incremental_capital if incremental_capital > 0 else None
    return dict(value=round(present,2), terminal=round(per_share,2), secondary=round(secondary,2),
                year5_parent_profit_bn=round(parent,3), year5_revenue_bn=round(sales,3),
                year5_cash_bn=round(cash,3),year5_debt_bn=round(debt,3), year5_book_bn=round(book,3),
                year5_parent_roe=round(parent/(book-parent),4), terminal_pe=round(multiple,3),
                group_incremental_operating_return=None if inc_return is None else round(inc_return,3),
                year1_to_5_incremental_capital_bn=round(incremental_capital,2),
                group_fcf_years_bn=[round(y["group_fcf"],2) for y in years])


def main():
    assert isclose(terminal_multiple(0,0.1,0.1),10)
    assert isclose(f["parent_equity"] + f["minority_equity"], f["group_equity"], abs_tol=1e-8)
    paths = {name:roll(s) for name,s in data["scenario_assumptions"].items()}
    values = [p["value"] for p in paths.values()]
    assert values == sorted(values) and min(values)>=0
    low, high = paths["base_low"], paths["base_high"]
    scenario = {"currency":"CNY", **{n:p["value"] for n,p in paths.items()},
                "horizon_note":"五年后成熟产线的产能、片均收入、折旧后毛利和无锡子公司利润共同决定终值，建设付款、融资成本与回售差额随路径变化。"}
    model = {"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"CNY","model_as_of":data["cutoff"],
             "base_case_distributions_per_share":c["distributions_per_share"],
             "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":low["terminal"],"high":high["terminal"]}}}
    out = {"symbol":data["symbol"],"report_period":data["report_period"],"value_range":{"currency":"CNY","low":low["value"],"high":high["value"]},
           "return_model":model,"scenarios":scenario,"paths":paths,"diluted_shares":stocks,
           "all_options_issued_upper_bound_shares":stocks+f["new_options"]}
    (DIR/"2026-Q3-output.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")


if __name__ == "__main__":
    main()
