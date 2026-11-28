"""运行 python 2026-H1.py，在脚本旁生成简明结果。"""
import json
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "2026-H1-input.json").read_text())
observed = data["observed"]
common = data["common"]
fx = data["fx"]
shares_start = data["issued"] + data["existing_awards"]


def price(distributions, terminal_cash, shares_end, rate, growth, dilution):
    # 成熟期按公平价值结算将来的持续股份奖励，普通股可分配额扣除稀释。
    terminal = terminal_cash * (1 + growth) / (rate - growth + dilution) / shares_end
    present_terminal = terminal / (1 + rate) ** len(distributions)
    value = present_terminal + sum(d / (1 + rate) ** i for i, d in enumerate(distributions, 1))
    return value, terminal, present_terminal / value


def project(path):
    cash = data["parent_liquidity"]
    available_cash = cash["at_june"] - sum(cash[k] for k in ("h2_buyback_allowance", "interim_cash_allowance", "bharti_maximum", "operating_floor"))
    special = min(cash["special_cap"], max(0, available_cash)) * path["special"]
    gross, shares = path["gross_first"], shares_start
    rows = []
    for year, growth in enumerate([0] + path["growth"]):
        gross *= 1 + growth
        new_capital = gross * path["strain"]
        costs = path["central"] * (1 + common["central_cost_growth"]) ** year
        minority = (gross - new_capital) * common["minority_fraction"]
        net = gross - new_capital - costs - minority
        distributable = (net * path["cash_conversion"] - path["financing_buffer"]) * path["return_fraction"]
        dps = min(path["dps_first"] * (1 + common["dividend_growth"]) ** year, distributable * 0.7 / shares)
        cash_dividends = shares * dps
        regular_buyback_budget = distributable - cash_dividends
        draw = min(special, max(0, common["gross_buyback_limit_year1"] - regular_buyback_budget)) if year == 0 else 0
        budget = distributable + draw
        buyback = budget - cash_dividends
        if year == 0:
            buyback = min(buyback, common["gross_buyback_limit_year1"])
        residual = budget - buyback - cash_dividends
        execution = path["execution_usd"] * (1 + common["execution_price_growth"]) ** year
        dilution = shares * common["gross_dilution_rate"]
        retired = buyback / execution - dilution
        assert buyback >= 0 and residual >= -1e-9 and shares > retired
        assert isclose(cash_dividends + buyback + residual, budget)
        rows.append(dict(dps=dps*fx, cash=distributable, capital=new_capital, net=net,
                         buyback=buyback, reserve_draw=draw, net_retired=retired, net_buyback_per_share=retired*execution*fx/shares,
                         shares=shares-retired))
        shares -= retired
    return rows


def outcome(path, rates):
    rows = project(path)
    dps = [row["dps"] for row in rows]
    return price(dps, rows[-1]["cash"]*fx, rows[-1]["shares"], rates["discount"],
                 rates["terminal_growth"], common["gross_dilution_rate"])


def embedded_value(index):
    check = data["cross_check"]
    # 六月底净存量剔商誉，补三季度税后新单贡献，扣截至估值日近似资本分配。
    existing = (observed["tev_no_goodwill"] - observed["ev_risk_shocks"][index]
                + observed["q3_nbp"] * common["nbp_common_fraction"]
                - check["post_june_buybacks_estimate"] - check["post_june_dividends_estimate"])
    annual_nbp = (observed["nine_month_nbp"] * 4/3 * common["nbp_common_fraction"]
                  * check["sustainable_nbp_fraction"][index])
    additional = sum(annual_nbp / (1 + check["discount"][index]) ** year for year in range(1, check["years"]+1))
    return (existing + additional) * fx / shares_start


assert isclose(price([10] * 5, 10, 1, 0.10, 0, 0)[0], 100)
assert observed["gross_ofsg_h1"] - observed["new_business_h1"] - observed["central_h1"] - observed["restructure_h1"] == observed["group_net_h1"]
assert observed["unit_remittances_h1"] - observed["parent_outflows_h1"] == observed["parent_net_h1"]
paths = data["paths"]
base = paths["base"]
rows = project(base)
endpoints = data["base_endpoints"]
low, high = (outcome(base, s) for s in endpoints.values())
anchors = {name: round(outcome(paths[name], paths[name])[0], 2) for name in ("structural_bear", "cyclical_bear", "bull")}
anchors.update(base_low=round(low[0], 2), base_high=round(high[0], 2))
sequence = [anchors[k] for k in ("structural_bear", "cyclical_bear", "base_low", "base_high", "bull")]
assert sequence == sorted(sequence)
result = dict(
    symbol="HK:02378", report_period="2026-H1", value_range={"low":sequence[2], "high":sequence[3], "currency":"HKD"},
    scenarios=anchors, return_model=dict(schema_version=1,method="annual_common_equity_irr_v1",currency="HKD",
    model_as_of=data["as_of"],base_case_distributions_per_share=[round(r["dps"],4) for r in rows],
    base_case_terminal_equity_value_range_per_share={"year_5":{"low":round(low[1],4),"high":round(high[1],4)}}),
    terminal_weight=[round(low[2],4),round(high[2],4)], cross_check=[round(embedded_value(i),2) for i in (0,1)],
    diluted_shares_m=round(shares_start,3), ending_shares_m=round(rows[-1]["shares"],3),
    base_y1= {k:round(v,4) for k,v in rows[0].items()}, base_y5={k:round(v,4) for k,v in rows[-1].items()},
    rate_plus_1pp=round(outcome(base,dict(discount=endpoints["low"]["discount"]+.01,terminal_growth=endpoints["low"]["terminal_growth"]))[0],2))
(HERE / "2026-H1-output.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
