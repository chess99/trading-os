"""在任意目录执行 python 2026-Q3.py，输出同目录的简明结果。"""
from pathlib import Path
import json
from math import isclose
from statistics import mean

root = Path(__file__).resolve().parent
data = json.loads((root / "2026-Q3-input.json").read_text())
facts = data["reported"]
fx = data["fx_hkd_per_usd"]
tangible = facts["group_equity"] - facts["minorities"] - facts["at1"] - facts["intangibles_net"]
assert isclose(tangible, 160.994)
opening_book = tangible - facts["detached_dividend"] - facts["buyback_post_quarter"]
opening_cet1 = facts["cet1"] - facts["buyback_post_quarter"]  # 季度监管资本已扣预计股息
opening_shares = facts["diluted_shares"] - facts["repurchased_shares"]
remaining_limit = facts["announced_buyback_limit"] - facts["buyback_post_quarter"]


def forecast(params):
    book, shares = opening_book, opening_shares
    cet1, rwa = opening_cet1, facts["rwa"]
    dividends, net_buybacks, gross_buybacks, net_shares, ratios = [], [], [], [], []
    for year, (rote, growth) in enumerate(zip(params["rote"], params["rwa_growth"])):
        profit = book * rote
        rwa *= 1 + growth
        pre_payout_capital = cet1 + params["conversion"] * profit
        headroom = max(0, pre_payout_capital - rwa * params["target_cet1"])
        dividend = min(profit * params["dividend_fraction"], headroom)
        limit = remaining_limit if year == 0 else params["later_buyback"]
        buyback = min(limit, headroom - dividend)
        execution = (facts["buyback_post_quarter"] / facts["repurchased_shares"]
                     if year == 0 else params["execution_ptbv"] * book / shares)
        cancelled = buyback / execution
        new_awards = params["new_awards"]
        dividends.append(dividend * fx / shares)
        net_buybacks.append((cancelled - new_awards) * execution * fx / shares)
        net_shares.append(cancelled - new_awards)
        gross_buybacks.append(buyback)
        next_book = book + profit - dividend - buyback
        next_shares = shares - cancelled + new_awards
        assert isclose(book + profit, next_book + dividend + buyback)
        assert next_shares > 0 and next_book > 0 and buyback >= 0
        book, shares = next_book, next_shares
        cet1 = pre_payout_capital - dividend - buyback
        assert cet1 + 1e-9 >= min(pre_payout_capital, rwa * params["target_cet1"])
        ratios.append(cet1 / rwa)
    return dividends, book * fx / shares, net_buybacks, net_shares, gross_buybacks, ratios


def present_value(dividends, final_book_per_share, steady_rote, cost, growth):
    # 稳态留存 g/RoTE，下一年度的收益以第五年末每股账本计算
    terminal = final_book_per_share * (steady_rote - growth) / (cost - growth)
    discounted_terminal = terminal / (1 + cost) ** len(dividends)
    value = discounted_terminal + sum(d / (1 + cost) ** t for t, d in enumerate(dividends, 1))
    return value, terminal, discounted_terminal / value


# 手算特例：留存为零，10元账本赚1元，收益率与贴现率均10%，股息加终值现值等于10元。
assert isclose(present_value([1] * 5, 10, 0.1, 0.1, 0)[0], 10)
results = {}
for key, params in data["assumptions"].items():
    divs, last_book, buys, shrinkage, gross, ratios = forecast(params)
    endpoints = params["steady_rote"]
    if not isinstance(endpoints, list):
        endpoints = [endpoints]
    values = [present_value(divs, last_book, roe, params["ke"], params["g"]) for roe in endpoints]
    results[key] = dict(value=[round(v[0], 2) for v in values], terminal=[round(v[1], 2) for v in values],
                        dividends=[round(x, 2) for x in divs], terminal_fraction=[round(v[2], 3) for v in values],
                        fifth_book=round(last_book, 2), annual_net_buyback_hkd=round(mean(buys), 3),
                        annual_net_shares_m=round(mean(shrinkage)*1000, 2), gross_buybacks_bn=[round(x, 3) for x in gross],
                        closing_cet1_pct=[round(x*100, 2) for x in ratios])
base = results["base"]
low, high = base["value"]
anchors = [results["structural"]["value"][0], results["cycle"]["value"][0], low, high, results["bull"]["value"][0]]
assert sorted(anchors) == anchors and anchors[0] > 0
check = data["cross_check"]
secondary = [
    round((opening_book * roe * check["capital_conversion"] - facts["rwa"] * check["growth"] * check["capital_requirement"])
          / (check["cost"] - check["growth"]) / opening_shares * fx, 2) for roe in check["rote"]
]
output = dict(symbol="HK:00005", report_period="2026-Q3", value_range=dict(low=low, high=high, currency="HKD"),
              return_model=dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD", model_as_of=data["as_of"],
                                base_case_distributions_per_share=base["dividends"],
                                base_case_terminal_equity_value_range_per_share={"year_5": dict(zip(["low", "high"], base["terminal"]))}),
              scenarios=dict(currency="HKD", **dict(zip(["structural_bear", "cyclical_bear", "base_low", "base_high", "bull"], anchors)),
                             horizon_note="各情景采用同一普通股起点，按盈利、风险资产、分配约束与持续回报分别折现至资料截止日。"),
              opening=dict(tangible_usd_bn=round(opening_book, 4), diluted_shares_bn=round(opening_shares, 6)),
              normalized_distributable_profit_hkd=secondary, paths=results)
(root / "2026-Q3-output.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
