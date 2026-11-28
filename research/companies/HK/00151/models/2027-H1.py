"""在任意目录执行 python /path/to/2027-H1.py，以同目录输入重建简明结果。"""
import json
from copy import deepcopy
from math import isclose
from pathlib import Path

folder = Path(__file__).resolve().parent
data = json.loads((folder / "2027-H1-input.json").read_text())
facts, policy = data["facts"], data["policy"]
fx = facts["cny_per_hkd"]


def present_value(dividends, terminal, rate):
    return sum(cash / (1 + rate) ** t for t, cash in enumerate(dividends, 1)) + terminal / (1 + rate) ** len(dividends)


def opening_bridge():
    post_cash = (facts["october_repurchase_hkd"] + sum(facts["november_repurchase_hkd"])) * fx
    net = facts["cash_and_bank"] + facts["long_deposits"] - facts["borrowings"]
    excess = net - post_cash - policy["operating_cash_buffer"] - facts["deferred_tax_liabilities"] - facts["unrecognised_remittance_tax"]
    legal = facts["march_parent_distributable_reserves"] - facts["september_dividend_paid"] - facts["h1_repurchase_hkd"] * fx - post_cash
    return {"net_cash": net, "post_purchase_cash": post_cash, "surplus_cash": excess, "initial_legal_proxy": legal,
            "economic_shares": facts["issued"] - facts["pending_cancellation"]}


def forecast(path, r, g):
    bridge = opening_bridge()
    sales = facts["sales_fy"] - facts["sales_prior_h1"] + facts["sales_h1"]
    cash, shares, legal = bridge["surplus_cash"], bridge["economic_shares"], bridge["initial_legal_proxy"]
    dividends, buybacks, checkpoints = [], [], []
    for year, (growth, margin) in enumerate(zip(path["growth"], path["margin"]), 1):
        extra_sales = sales * growth
        sales += extra_sales
        earnings = sales * margin * (1 - policy["operating_tax"])
        fixed = path["extra_fixed"] + max(0, extra_sales) * path["fixed_per_increment"]
        working = max(0, extra_sales) * path["working_per_increment"] + (path["channel_cash_first_year"] if year == 1 else 0)
        fcf = earnings - fixed - working
        interest = cash * policy["after_tax_cash_yield"]
        legal += policy["parent_access_to_new_operating_cash"] * max(0, fcf)
        dividend = min(legal, earnings * path["payout"], max(0, fcf + interest))
        buy = min(legal - dividend, earnings * path["buy_fraction"], max(0, fcf + interest - dividend))
        dividends.append(dividend / shares / fx)
        buybacks.append(buy / shares / fx)
        price = (earnings * policy["repurchase_earnings_multiple"] + cash) / shares
        retired = buy / price
        closing = cash + fcf + interest - dividend - buy
        assert isclose(closing + dividend + buy, cash + fcf + interest)
        assert 0 <= retired < shares and legal >= dividend + buy and closing >= 0
        shares -= retired
        legal -= dividend + buy
        cash = closing
        if year in (1, 5):
            checkpoints.append(dict(year=year, sales=sales, operating_net=earnings, net_fixed=fixed, working=working,
                                    fcf=fcf, shares=shares, surplus=cash, legal=legal, dividend=dividend, repurchase=buy))
    terminal_fcf = earnings * (1 + g) * (1 - g / policy["steady_roic"])
    accessible_cash = cash * ((1 + policy["after_tax_cash_yield"]) / (1 + r)) ** path["surplus_release_delay"]
    terminal = (terminal_fcf / (r - g) + accessible_cash) / shares / fx
    value = present_value(dividends, terminal, r)
    cross = [present_value(dividends, (earnings * k + accessible_cash) / shares / fx, r) for k in policy["earnings_crosscheck_range"]]
    return dict(value=value, dividends=dividends, terminal=terminal, terminal_pv_share=terminal / (1 + r) ** 5 / value,
                crosscheck=cross, avg_net_repurchase_hkd=sum(buybacks) / 5, checkpoints=checkpoints)


# 同一正式折现函数手算：各年付10，期末100，回报率10%，任意年数价值均为100。
assert isclose(present_value([10] * 5, 100, 0.1), 100)
runs = {}
for key in ("structural_bear", "cyclical_bear", "base_low", "base_high", "bull"):
    base = key.startswith("base_")
    path = data["paths"]["base" if base else key]
    rates = data["base_endpoints"][key] if base else path
    runs[key] = forecast(path, rates["r"], rates["g"])

anchors = {k: round(v["value"], 2) for k, v in runs.items()}
assert list(anchors.values()) == sorted(anchors.values())
lo, hi = runs["base_low"], runs["base_high"]
assert lo["dividends"] == hi["dividends"]
assert isclose(opening_bridge()["net_cash"], 11193.849)
stress = deepcopy(data["paths"]["base"])
stress["margin"] = [m - 0.01 for m in stress["margin"]]
middle = forecast(data["paths"]["base"], 0.096, 0.015)
sensitivity = forecast(stress, 0.096, 0.015)
output = dict(symbol=data["symbol"], report_period=data["report_period"],
              value_range=dict(currency="HKD", low=anchors["base_low"], high=anchors["base_high"]),
              scenarios=dict(currency="HKD", **anchors), bridge=opening_bridge(),
              return_model=dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD",
                                model_as_of=data["as_of"], base_case_distributions_per_share=[round(d, 4) for d in lo["dividends"]],
                                base_case_terminal_equity_value_range_per_share=dict(year_5=dict(low=round(lo["terminal"], 2), high=round(hi["terminal"], 2)))),
              annual_net_buyback_per_share=round(lo["avg_net_repurchase_hkd"], 4),
              middle_value=round(middle["value"], 3), margin_down_one_point=round(sensitivity["value"], 3),
              methods_two_range=[round(n, 2) for n in middle["crosscheck"]], paths=runs)
(folder / "2027-H1-output.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
