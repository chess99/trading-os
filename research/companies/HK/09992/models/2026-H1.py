"""泡泡玛特普通股模型。运行 python3 2026-H1.py，在脚本目录生成简明结果。"""
import json
from copy import deepcopy
from math import isclose
from pathlib import Path

folder = Path(__file__).resolve().parent
data = json.loads((folder / "2026-H1-input.json").read_text())
facts = data["facts"]
assumptions = data["assumptions"]
fx = facts["cny_per_hkd"]


def present_value(distributions, terminal, rate):
    return sum(cash / (1 + rate) ** year for year, cash in enumerate(distributions, 1)) + terminal / (1 + rate) ** len(distributions)


def opening_bridge():
    spent = sum(order["hkd"] for order in facts["repurchases"]) * fx / 1e6
    shares = (facts["issued_shares"] - sum(order["shares"] for order in facts["repurchases"]) + sum(facts["post_h1_awards"])) / 1e6
    group_deposits = facts["cash"] + facts["short_deposits"] + facts["long_deposits"]
    common_fraction = 1 - facts["nci_profit"] / facts["total_profit"]
    stub = assumptions["stub_sales"] * assumptions["stub_owner_cash_margin"] - assumptions["stub_extra_capital"]
    cash = (group_deposits - assumptions["initial_operating_cash"]) * common_fraction + stub - spent
    legal = facts["parent_reserves_fy"] - facts["h1_dps_cash"] - facts["h1_repurchase_cash"] - spent
    return dict(deposits_m=group_deposits, common_fraction=common_fraction, post_h1_repurchase_m=spent,
                stub_cash_m=stub, surplus_m=cash, parent_reserve_proxy_m=legal, shares_m=shares)


def forecast(path, rate, growth):
    bridge = opening_bridge()
    shares = bridge["shares_m"]
    subsidiary = bridge["surplus_m"]
    parent = 0.0  # 期后母公司账户未披露，富余资金均按待上划计。
    legal = bridge["parent_reserve_proxy_m"]
    previous_sales = assumptions["initial_revenue_reference"]
    dividends, net_buys, rows = [], [], []
    for sales, margin, extra in zip(path["revenue_m"], path["owner_margin"], path["extra_store_and_stock_m"]):
        opening_cash = parent + subsidiary
        earnings = sales * margin
        investment = max(0, sales - previous_sales) * path["capital_per_increment"] + extra
        execution = assumptions["buyback_execution_pe"] * earnings / shares
        awards = shares * assumptions["annual_issue_fraction"]
        noncash_pay = awards * execution
        generated = earnings - investment + noncash_pay
        subsidiary += generated
        wire = min(subsidiary, earnings * path["upstream_fraction"])
        withholding = wire * assumptions["remittance_tax"]
        subsidiary -= wire
        parent += wire - withholding
        legal += wire - withholding
        dividend = min(earnings * path["dividend_fraction"], legal, parent)
        repurchase = min(earnings * path["buyback_fraction"], parent - dividend, legal - dividend)
        dividends.append(dividend / shares / fx)
        net_buys.append((repurchase - noncash_pay) / shares / fx)
        parent -= dividend + repurchase
        legal -= dividend + repurchase
        shares += awards - repurchase / execution
        assert min(parent, legal, subsidiary) >= -1e-6
        assert isclose(parent + subsidiary, opening_cash + generated - withholding - dividend - repurchase)
        rows.append(dict(sales=sales, earnings=earnings, investment=round(investment, 3), net_shares_m=round(shares, 4)))
        previous_sales = sales
    usable = parent + subsidiary * (1 - assumptions["remittance_tax"]) / (1 + rate) ** path["release_lag"]
    normalized_cash = earnings * (1 + growth) * (1 - growth / path["terminal_roic"]) * (1 - assumptions["remittance_tax"])
    franchise = normalized_cash / (rate - growth)
    terminal = (franchise + usable) / shares / fx
    value = present_value(dividends, terminal, rate)
    alternative = []
    for key in ["method2_pe_low", "method2_pe_high"]:
        profit_value = sum(sales * weight * margin * multiple for weight, margin, multiple in
                           zip(assumptions["method2_weights"], assumptions["method2_owner_margins"], assumptions[key]))
        alt_terminal = (profit_value * (1 - assumptions["remittance_tax"]) + usable) / shares / fx
        alternative.append(round(present_value(dividends, alt_terminal, rate), 2))
    return dict(value=round(value, 2), dividends=[round(x, 4) for x in dividends], terminal=round(terminal, 2),
                terminal_pv_share=round(terminal / (1 + rate) ** 5 / value, 4), crosscheck=alternative,
                net_buy_hkd=round(sum(net_buys)/5, 4), retained_m=round(parent + subsidiary, 2),
                terminal_cash_m=round(usable, 2), y1_y5_incremental_capital_m=sum(x["investment"] for x in rows[1:]), years=rows)


assert isclose(present_value([10] * 5, 100, .1), 100)
assert sum(assumptions["method2_weights"]) == 1
assert facts["trust_included_june"] > facts["unvested_awards_june"] + sum(facts["post_h1_awards"])
paths = data["paths"]
runs = {k: forecast(p, p["r"], p["g"]) for k, p in paths.items()}
for key, (rate, growth) in data["endpoints"].items():
    runs[key] = forecast(paths["base"], rate, growth)
names = ["structural_bear", "cyclical_bear", "base_low", "base_high", "bull"]
anchors = {name: runs[name]["value"] for name in names}
assert list(anchors.values()) == sorted(anchors.values())
assert runs["base_low"]["dividends"] == runs["base_high"]["dividends"]
weaker = deepcopy(paths["base"])
weaker["owner_margin"] = [m - .03 for m in weaker["owner_margin"]]
no_buy = deepcopy(paths["base"])
no_buy["buyback_fraction"] = 0
base = runs["base"]
output = dict(symbol=data["symbol"], report_period=data["report_period"], value_range=dict(currency="HKD", low=anchors["base_low"], high=anchors["base_high"]),
              return_model=dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD", model_as_of=data["as_of"],
                                base_case_distributions_per_share=base["dividends"], base_case_terminal_equity_value_range_per_share=dict(
                                    year_5=dict(low=runs["base_low"]["terminal"], high=runs["base_high"]["terminal"]))),
              scenarios=dict(currency="HKD", **anchors), bridge=opening_bridge(), projection=base, alternative=base["crosscheck"],
              terminal_share_range=[runs[n]["terminal_pv_share"] for n in ["base_low", "base_high"]],
              sensitivity=dict(margin_down_3pp=forecast(weaker, weaker["r"], weaker["g"])["value"],
                               suspend_buyback=forecast(no_buy, no_buy["r"], no_buy["g"])["value"]))
(folder / "2026-H1-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
