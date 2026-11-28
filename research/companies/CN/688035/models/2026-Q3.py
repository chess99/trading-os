"""在此文件所在目录放置同名周期输入，运行 python 2026-Q3.py。金额为百万元。"""
from pathlib import Path
import json
from math import isclose

ROOT = Path(__file__).resolve().parent
INPUTS = json.loads((ROOT / "2026-Q3-input.json").read_text())


def present_value(dividends, terminal, rate):
    yearly = sum(amount / (1 + rate) ** year for year, amount in enumerate(dividends, 1))
    final = terminal / (1 + rate) ** len(dividends)
    return yearly + final, final


def transition(nopat, growth, p):
    """第六至十年利润增速收敛，经营资产的增量回报决定继续投入。"""
    pv = 0
    for year in range(1, 6):
        next_growth = growth + (p["stable_growth"] - growth) * year / 5
        increase = nopat * next_growth
        nopat += increase
        pv += (nopat - increase / p["roic"]) / (1 + p["rate"]) ** year
    stable_cash = nopat * (1 + p["stable_growth"] - p["stable_growth"] / p["roic"])
    return pv + stable_cash / (p["rate"] - p["stable_growth"]) / (1 + p["rate"]) ** 5


def model(data, p):
    b = data["basis"]
    shares = b["shares"]
    ownership = b["common_share_of_group"]
    claims = sum(b[k] for k in ["short_debt", "current_maturities", "long_debt", "lease", "acquisition_payable"])
    opening = (b["cash_equivalents"] + b["liquid_investments"] - claims - b["cash_floor"]) * ownership
    cash = opening
    earmarked = b["earmarked_cash"] * ownership
    sales = data["annualized_segment_sales"][:]
    income = sum(sales) * data["start_nopat_margin"]
    retained = 0
    checkpoints = []
    for year, dividend in enumerate(p["dividends"], 1):
        old_total, old_income = sum(sales), income
        sales = [old * (1 + g) for old, g in zip(sales, p["growth"], strict=True)]
        margin = data["start_nopat_margin"] + (p["margin"] - data["start_nopat_margin"]) * year / 5
        income = sum(sales) * margin
        increment = max(0, sum(sales) - old_total)
        investment = increment * (p["wc_per_growth"] + p["fixed_per_growth"])
        investment += data["yearly_extra_net_capex"][year-1] + p["losses"][year-1]
        net_cash = (income - investment) * ownership
        retained += net_cash - dividend * shares
        cash += net_cash - dividend * shares
        earmarked = max(0, earmarked - data["yearly_eligible_capex"][year-1] * ownership)
        assert cash >= earmarked and isclose(cash, opening + retained)
        checkpoints.append(round(net_cash, 2))
    assert earmarked == 0
    terminal = (income * p["multiple"] * ownership + cash) / shares
    explicit = (transition(income, income / old_income - 1, p) * ownership + cash) / shares
    pv, term_pv = present_value(p["dividends"], terminal, p["rate"])
    return {"present_value": round(pv, 2), "year_5_per_share": round(terminal, 2),
            "check_dcf_per_share": round(present_value(p["dividends"], explicit, p["rate"])[0], 2),
            "terminal_weight": round(term_pv / pv, 4), "year_5_sales": round(sum(sales), 2),
            "year_5_nopat": round(income, 2), "opening_parent_available": round(opening, 2),
            "year_5_retained_cash": round(cash, 2), "annual_parent_operating_free_cash": checkpoints}


def main():
    assert isclose(present_value([1, 1], 10, 0.1)[0], 10)
    d = INPUTS
    results = {k: model(d, p) for k, p in d["scenarios"].items()}
    anchors = {name: value["present_value"] for name, value in results.items()}
    assert list(anchors.values()) == sorted(anchors.values()) and min(anchors.values()) >= 0
    low, high = results["base_low"], results["base_high"]
    assert d["scenarios"]["base_low"]["dividends"] == d["scenarios"]["base_high"]["dividends"]
    output = {
        "symbol": d["symbol"], "report_period": d["period"], "currency": "CNY",
        "value_range": {"low": anchors["base_low"], "high": anchors["base_high"], "currency": "CNY"},
        "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY",
                         "model_as_of": d["cutoff"], "base_case_distributions_per_share": d["scenarios"]["base_low"]["dividends"],
                         "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low["year_5_per_share"], "high": high["year_5_per_share"]}}},
        "scenarios": {"currency": "CNY", **anchors, "horizon_note": "五年普通股分配与第五年经营价值、留存现金折现。结构性竞争和周期逆风下分别下调产品增速、利润率和派息，并增加应收、存货损耗及单位销售所需投入。"},
        "details": results
    }
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
