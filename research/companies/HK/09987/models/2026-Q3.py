"""百胜中国每股价值。经营与资本预算均以百万美元计。"""
import json
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "2026-Q3-input.json").read_text())


def equity_path(d, p):
    shares = d["issued"] - d["pending_retirement"] + d["incremental_awards"]
    cash = (d["cash_investments"] - d["borrowings"] - d["finance_leases_budget"]
            - d["liquidity_reserve"] - d["post_quarter_repurchases_budget"])
    revenue = d["revenue_ttm"]
    dividends, budget = [], []
    for year, growth in enumerate(p["growth"], start=1):
        opening_shares = shares
        growth_revenue = revenue * growth
        revenue += growth_revenue
        margin = d["ebit_margin_ttm"] + year / 5 * (p["margin"] - d["ebit_margin_ttm"])
        parent_profit = revenue * margin * (1 - d["tax"]) * d["parent_share"]
        capital = (revenue * (p["capex_rate"] - d["depreciation_rate"])
                   + growth_revenue * d["incremental_working_capital_rate"]) * d["parent_share"]
        equity_pay = revenue * d["sbc_rate"] * d["parent_share"]
        free_cash = parent_profit - capital + equity_pay
        dividend = free_cash * p["dividend_share"]
        buyback_budget = free_cash * p["buyback_share"]
        price = p["multiple"] * parent_profit / shares
        gross_removed = buyback_budget / 1.01 / price
        awarded = equity_pay / price
        shares += awarded - gross_removed
        cash += free_cash - dividend - buyback_budget
        assert isclose(shares - opening_shares, awarded - gross_removed, abs_tol=1e-10)
        assert isclose(dividend + buyback_budget + free_cash * (1-p["dividend_share"]-p["buyback_share"]), free_cash)
        assert cash >= 0 and shares > 0
        dividends.append(dividend / opening_shares * d["fx"])
        budget.append({"profit":parent_profit, "fcf":free_cash, "cash":cash, "capex":revenue*p["capex_rate"],
                       "shares":shares, "gross_removed":gross_removed, "awarded":awarded,
                       "net_buyback_per_share":(gross_removed-awarded)*price/opening_shares*d["fx"]})
    g, r = p["terminal_growth"], p["rate"]
    mature_fcf = parent_profit * (1+g) * (1-g/p["terminal_roic"])
    terminal = (mature_fcf/(r-g) + cash) / shares * d["fx"]
    def present(tv):
        return sum(div/(1+r)**t for t,div in enumerate(dividends,1)) + tv/(1+r)**5
    return {"value":present(terminal), "terminal":terminal, "dividends":dividends, "budget":budget,
            "terminal_pv_fraction":terminal/(1+r)**5/present(terminal),
            "cross_low":present((14*parent_profit+cash)/shares*d["fx"]),
            "cross_high":present((17*parent_profit+cash)/shares*d["fx"])}


def run(d):
    # 无增长、无多余资产、当期盈利全分，100 股平分 100 美元，折现率 10%。
    flat = dict(d, issued=100, pending_retirement=0, incremental_awards=0, revenue_ttm=100,
                ebit_margin_ttm=1, tax=0, parent_share=1, depreciation_rate=0, sbc_rate=0,
                cash_investments=0, borrowings=0, finance_leases_budget=0, liquidity_reserve=0,
                post_quarter_repurchases_budget=0, fx=1)
    test = dict(d["paths"]["base_low"], growth=[0]*5, margin=1, capex_rate=0, dividend_share=1,
                buyback_share=0, rate=.1, terminal_growth=0)
    assert isclose(equity_path(flat,test)["value"], 10)
    paths = {k:equity_path(d,v) for k,v in d["paths"].items()}
    value = {k:round(x["value"],2) for k,x in paths.items()}
    assert list(value.values()) == sorted(value.values())
    low,high = paths["base_low"],paths["base_high"]
    return {
        "symbol": "HK:09987", "report_period": "2026-Q3",
        "value_range":{"low":value["base_low"],"high":value["base_high"],"currency":"HKD"},
        "scenarios_hkd":value,
        "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"HKD",
                        "model_as_of":d["as_of"],"base_case_distributions_per_share":[round(x,2) for x in low["dividends"]],
                        "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":round(low["terminal"],2),"high":round(high["terminal"],2)}}},
        "cross_check_hkd":[round(low["cross_low"],2),round(high["cross_high"],2)],
        "terminal_pv_fraction":[round(p["terminal_pv_fraction"],3) for p in [low,high]],
        "base_years":[{k:round(v,3) for k,v in row.items()} for row in low["budget"]],
        "sensitivity_margin_minus_1pp":round(equity_path(d,dict(d["paths"]["base_low"],margin=d["paths"]["base_low"]["margin"]-.01))["value"],2)
    }


if __name__ == "__main__":
    out = run(DATA)
    (HERE/"2026-Q3-output.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
