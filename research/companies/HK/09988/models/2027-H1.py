"""在本目录执行 python3 2027-H1.py，读取同名 input.json 并生成 output.json。"""
import json
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent


def discounted(cash, terminal, rate):
    years = len(cash)
    return sum(payment / (1 + rate) ** year for year, payment in enumerate(cash, 1)) + terminal / (1 + rate) ** years


def interpolate(pair, fraction):
    return pair[0] + (pair[1] - pair[0]) * fraction


def run(data, case):
    f, c = data["facts"], data["common"]
    rate, growth = case["discount"], case["g"]
    assert 0 <= growth < rate and growth < case["roic"]
    # 期末经济流通股：承接三月法定与GAAP股数差，两期GAAP库存股成本接近。
    shares = f["issued"] - (f["march_issued"] - f["march_economic"])
    shares += f["rsus"] + f["post_period_awards"] + f["options"]
    plain_debt = f["short_bank"] + f["long_bank"] + f["senior_notes"] + f["exchangeable"]
    debt = plain_debt + f["convertibles"]
    net_portfolio = (f["equity_investments_current"] + f["equity_investments_long"]
                     - f["liquid_treasury_in_investments"] + f["associates"]) * case["portfolio_recovery"]
    other_claims = f["minority"] + f["mezzanine"]
    commerce, cloud = c["commerce_reference"], c["cloud_reference"]
    cash = f["cash"] - c["reserve"]
    dividends, forward_fcf, checkpoints = [], [], {}
    total_investment = 0
    for year in range(1, 11):
        t = min((year - 1) / 4, 1)
        fade = max(0, (year - 5) / 5)
        old_sales = commerce + cloud
        commerce *= 1 + interpolate([case["commerce_cagr"], growth], fade)
        cloud *= 1 + interpolate([case["cloud_cagr"], growth], fade)
        commerce_ebita = commerce * interpolate(case["commerce_margin"], t)
        cloud_ebita = cloud * interpolate(case["cloud_margin"], t)
        # 成熟期费用按收入同步增长，使远期利润率稳定。
        if year == 5:
            sales_five = commerce + cloud
        cost_scale = (commerce + cloud) / sales_five if year > 5 else 1
        residual_cost = (interpolate(case["other_losses"], t) + c["sbc_cash_equivalent"]) * cost_scale
        nopat = (commerce_ebita + cloud_ebita - residual_cost) * (1 - c["tax"])
        net_plant = interpolate(case["net_plant"], t)
        wc = max(0, commerce + cloud - old_sales) * c["working_investment_rate"]
        # 扩建与周转由显性预算向长期增量资本收益率逐步过渡。
        investment = interpolate([net_plant + wc, nopat * growth / case["roic"]], fade)
        fcf = nopat - investment
        if year <= 5:
            start = cash
            funding = cash * (c["cash_rate"] if cash >= 0 else rate) - debt * c["debt_aftertax_rate"]
            max_dividend = max(0, cash + fcf + funding)
            paid = min(c["dividend_per_share_cny"][year - 1] * case["dividend_factor"] * shares, max_dividend)
            cash += fcf + funding - paid
            assert isclose(start + fcf + funding, cash + paid, abs_tol=1e-8)
            dividends.append(paid / shares / f["hkd_in_cny"])
            total_investment += investment
        else:
            forward_fcf.append(fcf)
        if year in (1, 5):
            checkpoints[year] = {"commerce":commerce,"cloud":cloud,"nopat":nopat,"fcf":fcf,"cash_above_reserve":cash,"invested":total_investment,"investment":investment}
    year10_terminal = nopat * (1 + growth) * (1 - growth / case["roic"]) / (rate - growth)
    year5_business = discounted(forward_fcf, year10_terminal, rate)
    bridge = cash + net_portfolio - other_claims - debt

    def equity_per_share(business):
        debt_case = (business + bridge) / shares
        # 两档转债分别评估，以本金和最高兑换股份作为保守条款代理。
        # 第一档调整后最高股数、第二档最高股数取十月月报。
        tranches = f["conversion_tranches"]
        total_principal_usd = sum(tranche["usd_principal"] for tranche in tranches)
        blocks = [(f["convertibles"] * tranche["usd_principal"] / total_principal_usd, tranche["max_shares"])
                  for tranche in tranches]
        settle = [debt_case]
        for converted in ([blocks[0]], [blocks[1]], blocks):
            principal, dilution = map(sum, zip(*converted))
            settle.append((business + bridge + principal) / (shares + dilution))
        return max(0,min(settle)) / f["hkd_in_cny"]

    terminal = equity_per_share(year5_business)
    value = discounted(dividends, terminal, rate)
    alternative = discounted(dividends, equity_per_share(checkpoints[5]["nopat"] * case["multiple"]), rate)
    return {"value":round(value,2),"terminal":round(terminal,2),"dividends":[round(v,4) for v in dividends],
            "alternative":round(alternative,2),"year5_pv_fraction":round(terminal / (1 + rate)**5 / value,4),
            "diluted_before_conversion":round(shares,5),"portfolio":round(net_portfolio,2),
            "years":{str(y):{k:round(v,2) for k,v in row.items()} for y,row in checkpoints.items()}}


def main():
    data = json.loads((HERE / "2027-H1-input.json").read_text())
    assert isclose(discounted([10,10],100,.1),100)
    facts = data["facts"]
    net_award_issuance = sum(facts["rsu_issued_monthly"]) - facts["cancelled"]
    assert isclose(facts["march_issued"] + facts["placement_shares"] + net_award_issuance, facts["issued"])
    results = {k:run(data, s) for k,s in data["cases"].items()}
    anchors = {name:row["value"] for name,row in results.items()}
    assert list(anchors.values()) == sorted(anchors.values())
    low, high = results["base_low"], results["base_high"]
    assert low["dividends"] == high["dividends"]
    output = {"symbol":data["symbol"],"report_period":data["report_period"],
              "value_range":{"low":low["value"],"high":high["value"],"currency":"HKD"},
              "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"HKD",
                              "model_as_of":data["as_of"],"base_case_distributions_per_share":low["dividends"],
                              "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":low["terminal"],"high":high["terminal"]}}},
              "anchors":anchors,"paths":results,
              "net_award_issuance_after_buyback_bn":round(net_award_issuance,8),
              "sensitivity_base_low":{
                  "discount_plus_one_point":run(data, {**data["cases"]["base_low"],"discount":.108})["value"],
                  "cloud_margin_year5_minus_five_points":run(data, {**data["cases"]["base_low"],"cloud_margin":[.132,.13]})["value"]}}
    (HERE / "2027-H1-output.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')


if __name__ == "__main__":
    main()
