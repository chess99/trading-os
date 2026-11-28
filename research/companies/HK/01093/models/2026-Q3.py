"""运行 python 2026-Q3.py；读取同目录输入并写回简明结果。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / "2026-Q3-input.json").read_text())
facts = data["facts"]
policy = data["policy"]


def bridge():
    cash = facts["cash"] + facts["structured"] - facts["restricted"]
    obligations = sum(facts[key] for key in (
        "banks", "leases", "refundable", "dividend_july", "capital_payable", "partnership_commitments"))
    november = facts["dividend_november_hkd"] * facts["issued_m"] * facts["fx_cny_per_hkd"]
    surplus = cash - obligations - november - policy["operating_buffer"]
    available = surplus * (1 - facts["nci"] / facts["net_assets"]) * (1 - policy["remittance_tax_excess"])
    assert 0 <= available <= surplus <= cash
    return available


def present_value(payments, terminal, rate):
    return sum(x / (1 + rate) ** t for t, x in enumerate(payments, 1)) + terminal / (1 + rate) ** len(payments)


def project(s):
    goods = facts["goods_fy25"] + facts["goods_9m26"] - facts["goods_9m25"]
    drug = facts["drug_fy25"] + facts["drug_9m26"] - facts["drug_9m25"]
    other = goods - drug
    denominator = (facts["issued_m"] + facts["options_m"]) * facts["fx_cny_per_hkd"]
    starting_cash = bridge()
    cash = starting_cash
    dividends, profits, free_cash, capital, research, sales = [], [], [], [], [], []
    for g in s["drug_growth"]:
        previous_goods = goods
        drug *= 1 + g
        other *= 1 + s["other_growth"]
        goods = drug + other
        rd = goods * s["rd_as_goods"]
        product = (goods * s["goods_margin_before_rd"] - rd) * (1 - policy["nci_goods"])
        fees = s["licence"] * s["licence_contribution"] * (1 - policy["nci_licence"])
        profit = (product + fees) * (1 - s["tax"])
        # 不提前释放销量下降带来的存货；资本支出含固定资产和外购无形资产。
        investment = (goods * (s["capex_as_goods"] - policy["dep_as_goods"])
                      + max(0, goods - previous_goods) * s["wc_share"]) * (1 - policy["nci_goods"])
        fcfe = profit - investment
        payout = max(0, fcfe * s["payout"])
        cash += fcfe - payout
        assert cash >= 0
        dividends.append(payout / denominator)
        profits.append(profit)
        free_cash.append(fcfe)
        capital.append(investment)
        research.append(rd)
        sales.append(goods)
    assert abs(cash - (starting_cash + sum(free_cash) - sum(dividends) * denominator)) < 1e-5
    terminals = [(multiple * profits[-1] + cash) / denominator for multiple in s["terminal_pe"]]
    values = [present_value(dividends, terminal, s["discount"]) for terminal in terminals]
    return dict(values=values, terminals=terminals, dividends=dividends, profit=profits, fcfe=free_cash,
                net_investment=capital, rd=research, goods=sales, end_cash=cash, starting_cash=starting_cash,
                terminal_share=[(t / (1+s["discount"])**5) / v for t, v in zip(terminals, values)])


def mature_cashflow(s, detail):
    # 第6—10年盈利增速渐降；普通股再投资为次年增长所需的新增权益资本。
    growth_path = [.055, .05, .045, .035, .03]
    ke = s["discount"]
    earnings = detail["profit"][-1]
    future = []
    for growth in growth_path:
        next_earnings = earnings * (1 + growth)
        future.append(next_earnings - (next_earnings - earnings) / policy["steady_roe"])
        earnings = next_earnings
    g = policy["steady_growth"]
    steady_cash = earnings * (1 + g) * (1 - g / policy["steady_roe"])
    terminal = present_value(future, steady_cash / (ke - g), ke)
    denominator = (facts["issued_m"] + facts["options_m"]) * facts["fx_cny_per_hkd"]
    return present_value(detail["dividends"], (terminal + detail["end_cash"]) / denominator, ke)


def rounded(x):
    return [round(y, 4) for y in x]


assert abs(present_value([1, 1], 10, .1) - 10) < 1e-10
runs = {key: project(params) for key, params in data["scenarios"].items()}
base = runs["base"]
anchors = dict(structural_bear=round(runs["structural_bear"]["values"][0], 2),
               cyclical_bear=round(runs["cyclical_bear"]["values"][0], 2),
               base_low=round(base["values"][0], 2), base_high=round(base["values"][1], 2),
               bull=round(runs["bull"]["values"][0], 2))
assert list(anchors.values()) == sorted(anchors.values())
model = dict(schema_version=1, method="annual_common_equity_irr_v1", currency="HKD",
             model_as_of=data["information_cutoff"], base_case_distributions_per_share=rounded(base["dividends"]),
             base_case_terminal_equity_value_range_per_share={"year_5": dict(zip(("low", "high"), rounded(base["terminals"])))})
out = dict(symbol=data["symbol"], report_period=data["report_period"],
           value_range=dict(low=anchors["base_low"], high=anchors["base_high"], currency="HKD"),
           return_model=model, scenarios=anchors, cash_bridge_m=round(bridge(), 2),
           cross_check=round(mature_cashflow(data["scenarios"]["base"], base), 2),
           operating_cases={k: {m: rounded(v[m]) for m in ("profit","rd","goods","fcfe","net_investment","terminal_share")} for k, v in runs.items()},
           sensitivities={})
for key, delta in [("licence", -500), ("rd_as_goods", .01), ("goods_margin_before_rd", -.01), ("discount", .01)]:
    case = dict(data["scenarios"]["base"])
    case[key] += delta
    out["sensitivities"][key] = rounded(project(case)["values"])
out["sensitivities"]["full_scheme_zero_proceeds"] = rounded([
    v * (facts["issued_m"] + facts["options_m"]) /
    (facts["issued_m"] + facts["options_m"] + facts["ungranted_mandate_m"]) for v in base["values"]
])
(ROOT / "2026-Q3-output.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
