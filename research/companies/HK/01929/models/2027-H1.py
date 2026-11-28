"""python3 2027-H1.py 读取同目录输入并重建结果。金额和股数均以十亿计。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).parent
PERIOD = "2027-H1"


def present(distributions, terminal, rate):
    years = len(distributions)
    return sum(cash / (1 + rate) ** year for year, cash in enumerate(distributions, 1)) + terminal / (1 + rate) ** years


def path(f, s, converted, endpoint):
    sales = f["annual_sales"] - f["old_h1_sales"] + f["h1_sales"]
    original_shares = f["issued_shares"] - f["treasury_shares"] + f["unvested_awards"]
    shares = original_shares
    cash_reserve = f["cash"] - f["minimum_cash"]
    distributions = []
    traces = []
    for year, (growth, margin, funding) in enumerate(zip(s["growth"], s["margin"], s["extra_funding"]), 1):
        new_sales = sales * (1 + growth)
        invest = max(0, new_sales - sales) * s["capital_per_new_sale"] + funding
        redemption = 0
        if year == 2 and not converted:
            redemption = f["convertible_face"] * f["put_at_par"] - s["refinance"]
        if year >= 3 and converted:
            shares = original_shares + f["conversion_shares"]
        # 2028年6月落在第二预测年；以年末近似结算，下一年起用替代融资成本。
        finance = f["convertible_face"] * f["coupon"] if year < 3 else (0 if converted else s["refinance"] * s["interest"])
        earnings = new_sales * margin - finance
        total_cash = cash_reserve + earnings - invest - redemption
        distribution = min(earnings * s["payout"], max(0, total_cash))
        if year == 1:
            distribution = max(distribution, f["approved_interim"] * f["issued_shares"])
        ending = total_cash - distribution
        assert ending >= -1e-9
        assert isclose(cash_reserve + earnings, ending + distribution + invest + redemption, abs_tol=1e-9)
        cash_reserve = ending
        distributions.append(distribution / shares)
        traces.append([round(n,3) for n in (new_sales,earnings,invest,redemption,ending)])
        sales = new_sales
    growth = s["terminal_growth"][endpoint]
    discount = s["discount"][endpoint]
    assert 0 <= growth < discount
    # 假设稳态维持债务/收入，保守地按销售增速放大融资费用。
    cash_y6 = earnings * (1 + growth) - sales * growth * s["capital_per_new_sale"]
    terminal = (cash_y6 / (discount - growth) + cash_reserve) / shares
    value = present(distributions, terminal, discount)
    return {"value":value,"terminal":terminal,"terminal_pv_fraction":terminal / (1 + discount)**5 / value,
            "dividends":distributions,"trace":traces,"bond":"转股" if converted else "回售"}


def calculate(data):
    f = data["facts"]
    assert isclose(f["common_equity"] + f["minority_equity"], f["group_equity"])
    assert isclose(present([1,1], 10, 0.1), 10)
    assert isclose(f["convertible_face"] / 15.52, f["conversion_shares"], abs_tol=1e-8)
    # 无融资、无增长、全部派息的单股企业，每年赚1港元、折现10%，每股价值10港元。
    toy_facts = {**f,"annual_sales":10,"old_h1_sales":0,"h1_sales":0,"cash":0,"minimum_cash":0,
                 "issued_shares":1,"unvested_awards":0,"convertible_face":0,"approved_interim":0}
    toy_case = {**data["scenarios"]["base"],"growth":[0]*5,"margin":[0.10]*5,"extra_funding":[0]*5,
                "payout":1,"refinance":0,"discount":[0.10]*2,"terminal_growth":[0]*2}
    assert isclose(path(toy_facts,toy_case,False,0)["value"],10)
    values = {}
    for name, s in data["scenarios"].items():
        values[name] = []
        for endpoint in (0,1):
            alternatives = [path(f,s,converted,endpoint) for converted in (False,True)]
            redemption, conversion = alternatives
            # 以回售日临近的第二年末，每一元债券对应的转股权益与现金回售价比较。
            value_at_put = present(conversion["dividends"][2:], conversion["terminal"], s["discount"][endpoint])
            will_convert = value_at_put * f["conversion_shares"] > f["convertible_face"] * f["put_at_par"]
            selected, other = (conversion, redemption) if will_convert else (redemption, conversion)
            values[name].append({**selected,"alternative":round(other["value"],2),"at_put":round(value_at_put,2)})
    base = values["base"]
    assert base[0]["dividends"] == base[1]["dividends"]
    scen = {"structural_bear":values["structural_bear"][0]["value"],"cyclical_bear":values["cyclical_bear"][0]["value"],
            "base_low":base[0]["value"],"base_high":base[1]["value"],"bull":values["bull"][0]["value"]}
    assert list(scen.values()) == sorted(scen.values())
    v = {"low":round(scen["base_low"],2),"high":round(scen["base_high"],2),"currency":"HKD"}
    c = data["cross_check"]
    net_book = f["common_equity"] - (f["convertible_face"] * f["put_at_par"] - f["bond_carrying"])
    book_per_share = net_book / (f["issued_shares"] + f["unvested_awards"] - f["treasury_shares"])
    cross = [round(book_per_share * (roe - c["growth"]) / (cost - c["growth"]),2)
             for roe,cost in zip(c["normal_roe"],c["cost_of_equity"])]
    funding_case = {**data["scenarios"]["base"],"capital_per_new_sale":0.63}
    margin_case = {**data["scenarios"]["base"],"margin":[m-0.01 for m in data["scenarios"]["base"]["margin"]]}
    sensitivities = {label:[round(path(f,case,False,i)["value"],2) for i in (0,1)]
                     for label,case in (("margin_minus_1pp",margin_case),("capital_plus_0.20",funding_case))}
    return {"sensitivity":sensitivities,"symbol":data["symbol"],"report_period":PERIOD,"value_range":v,
            "scenarios":{"currency":"HKD",**{key:round(value,2) for key,value in scen.items()}},
            "return_model":{"schema_version":1,"method":"annual_common_equity_irr_v1","currency":"HKD","model_as_of":data["cutoff"],
                            "base_case_distributions_per_share":[round(x,4) for x in base[0]["dividends"]],
                            "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":round(base[0]["terminal"],3),"high":round(base[1]["terminal"],3)}}},
            "cross_check":cross,"book_per_share_after_put":round(book_per_share,3),
            "base_terminal_pv_fraction":[round(x["terminal_pv_fraction"],3) for x in base],
            "base_trace_sales_profit_reinvestment_put_reserve":base[0]["trace"],
            "bond_cases":{k:[(x["bond"],round(x["value"],2),x["alternative"],x["at_put"]) for x in [a[0],a[1]]] for k,a in values.items()}}


if __name__ == "__main__":
    model = json.loads((ROOT / f"{PERIOD}-input.json").read_text())
    output = calculate(model)
    (ROOT / f"{PERIOD}-output.json").write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n")
