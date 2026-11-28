"""运行 python 2026-H1.py，依同目录输入重算每股现值、分配与终值。"""
import json
import math
from pathlib import Path

directory = Path(__file__).resolve().parent
data = json.loads((directory / "2026-H1-input.json").read_text())
opening = data["opening"]
share_count = opening["issued_billion"] + opening["option_allowance_billion"]
per_share = opening["fx"] / share_count
opening_debt = (opening["sep_senior_notes"] + opening["sep_term_loan"] + opening["sep_revolver"]
                - opening["sep_cash"] + opening["october_dividend"] + opening["issue_cost"]
                + opening["operating_cash_floor"])


def pv(flows, residual, rate):
    discounted_flows = sum(cash / (1 + rate) ** year for year, cash in enumerate(flows, 1))
    return discounted_flows + residual / (1 + rate) ** len(flows)


def value(path):
    debt = opening_debt
    payouts = []
    for year, (sales, margin) in enumerate(zip(path["sales"], path["margin"])):
        company_cash = (sales * (margin - path["corporate_rate"])
                        - path["qualified_investment"] - path["ordinary_capital"][year]
                        - path["working_capital"] - path["lease_license"] - path["cash_tax"][year])
        equity_cash = company_cash - max(debt, 0) * path["debt_rate"]
        distribution = max(0, equity_cash) * path["payout"]
        # 削减在压力路径中会使债务进一步上升的派息；实际续借仍须满足信贷契约。
        if debt > 3.5 * sales * margin:
            distribution = 0.0
        new_debt = debt - equity_cash + distribution
        assert math.isclose(debt - new_debt + distribution, equity_cash, abs_tol=1e-11)
        payouts.append(distribution)
        debt = new_debt

    franchise_years = path["renewal_years"]
    property_residual = opening["property_mark"] * path["residual_fraction"]
    renewal_cash = company_cash - path["renewal_annual_charge"]
    year6_ev = pv([renewal_cash] * franchise_years, property_residual, path["unlevered_rate"])
    year6_equity = max(year6_ev - debt, 0)
    r = path["equity_rate"]
    year5_equity = (payouts[5] + year6_equity) / (1 + r)
    current = pv(payouts[:5], year5_equity, r)
    assert math.isclose(current, pv(payouts, year6_equity, r), abs_tol=1e-10)
    return {"value":current * per_share, "terminal":year5_equity * per_share,
            "distributions":[v * per_share for v in payouts[:5]], "year6_debt":debt,
            "terminal_fraction":year5_equity / (1+r)**5 / current if current else 0.0, "year6_unlevered_cash":company_cash}


assert math.isclose(pv([10,10],100,.1),100)
assert math.isclose(pv([],12,.1),12)
values = {key:value(path) for key,path in data["paths"].items()}
anchors = {key:round(case["value"],2) for key,case in values.items()}
ordered = [anchors[k] for k in ("structural_bear","cyclical_bear","base_low","base_high","bull")]
assert ordered == sorted(ordered) and min(ordered) >= 0
low, high = values["base_low"], values["base_high"]
assert low["distributions"] == high["distributions"]
second = data["secondary"]
alt = [(second["normalized_sales"] * (margin - second["overhead_rate"]) * multiple
        - opening_debt) * per_share for margin,multiple in zip(second["margins"],second["multiple"])]
base = data["paths"]["base_low"]
more_capital = dict(base,ordinary_capital=[x+.10 for x in base["ordinary_capital"]])
no_renewal = dict(base,renewal_years=0)
result = {"symbol":data["symbol"],"report_period":data["report_period"],
          "value_range":{"low":anchors["base_low"],"high":anchors["base_high"],"currency":"HKD"},
          "return_model":{"method":"annual_common_equity_irr_v1","schema_version":1,"currency":"HKD",
                          "model_as_of":data["cutoff"],"base_case_distributions_per_share":[round(v,4) for v in low["distributions"]],
                          "base_case_terminal_equity_value_range_per_share":{"year_5":{"low":round(low["terminal"],4),"high":round(high["terminal"],4)}}},
          "anchors":anchors,"effective_debt_usd_bn":round(opening_debt,3),"diluted_shares_bn":round(share_count,6),
          "terminal_value_pct":[round(v["terminal_fraction"]*100,1) for v in (low,high)],
          "year6_remaining_debt_usd_bn":round(low["year6_debt"],3),
          "alternative_hkd":[round(v,2) for v in alt],
          "sensitivity_base_low_hkd":{"extra_annual_capital_usd_100m":round(value(more_capital)["value"],2),
                                      "no_concession_after_2032":round(value(no_renewal)["value"],2)}}
(directory / "2026-H1-output.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
