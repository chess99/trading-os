"""在当前目录或任意工作目录运行本文件，使用同目录输入复算。"""
import json
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent


def segment_flow(revenue, margin, previous_wc, wc_ratio, net_capex, recovery):
    target_wc = revenue * wc_ratio
    change = target_wc - previous_wc
    loss = max(-change, 0) * (1 - recovery)
    cash = revenue * (margin - net_capex) - change - loss
    assert isclose(cash + target_wc + loss, revenue * (margin - net_capex) + previous_wc)
    return cash, target_wc


def common_value(total, basic, face, strike):
    # 将债权人保底偿付与转股权同时列出。保守地按面值处理保底偿还。
    fully_diluted = basic + face / strike
    as_converted = total / fully_diluted
    payoff_shortfall = max(0, face - as_converted * face / strike)
    price = as_converted - payoff_shortfall / basic
    assert isclose(price, min(as_converted, (total - face) / basic))
    return max(0, price)


def calculate(data, scenario):
    p = data["paths"][scenario]
    f = data["facts"]
    rate = p["discount"]
    bridge = f["cash_equivalents"] - sum(f[k] for k in (
        "short_debt", "long_debt", "current_maturities", "lease_long", "purchase_cash_due", "tax_payable"
    )) - data["operating_cash_floor"]
    assert isclose(f["registered_shares"], f["sep_shares"] + f["registered_issued"])
    basic = f["registered_shares"] + data["employee_net_increment"]
    wc = sum(f[k] for k in ("inventory", "receivables", "bills", "bill_financing", "prepayment"))
    wc -= f["payables"] + f["contract_liabilities"]
    present, alternate = bridge, bridge
    terminal_pv = 0
    for i, segment in enumerate(("legacy", "shm")):
        start, end, first_margin, last_margin = p[segment]
        previous_wc = wc * f[segment + "_9m"] / (f["legacy_9m"] + f["shm_9m"])
        wc_after_two = 0
        last_year = 5 if segment == "legacy" else p["shm_last_year"]
        for year in range(1, last_year + 1):
            step = min(year - 1, 4) / 4
            revenue = start + (end - start) * step
            if year > 5:
                revenue *= (1 + p["shm_after_growth"]) ** (year - 5)
            margin = first_margin + (last_margin - first_margin) * step
            cash, previous_wc = segment_flow(revenue, margin, previous_wc, p["wc"][i],
                                             p["capex"][i], p["release"])
            if year == 2:
                wc_after_two = previous_wc
            if segment == "shm" and year == last_year:
                cash += previous_wc * p["release"]
            discount = (1 + rate) ** year
            present += cash / discount
            if segment == "legacy" or year <= 2:
                alternate += cash / discount
            if year > 5:
                terminal_pv += cash / discount
        if segment == "legacy":
            terminal = end * last_margin * p["multiple"] / (1 + rate) ** 5
            present += terminal
            terminal_pv += terminal
            growth = p["alt_growth"]
            sustainable_fcf = end * last_margin * (1 + growth) * (1 - growth / p["alt_roic"])
            alternate += sustainable_fcf / (rate - growth) / (1 + rate) ** 5
        else:
            units_revenue = p["alt_shm_units"] * p["alt_shm_price"]
            for year in range(3, last_year + 1):
                cash, wc_after_two = segment_flow(units_revenue, p["alt_shm_margin"], wc_after_two,
                                                   p["wc"][i], p["capex"][i], p["release"])
                if year == last_year:
                    cash += wc_after_two * p["release"]
                alternate += cash / (1 + rate) ** year
    own = lambda x: common_value(x, basic, f["convertible"], f["conversion_price"])
    return {"per_share": round(own(present), 2), "crosscheck_per_share": round(own(alternate), 2),
            "year5_terminal_pv_fraction": round(terminal_pv / present, 4),
            "net_cash_bridge": round(bridge, 4), "opening_wc": round(wc, 4),
            "diluted_shares": round(basic + f["convertible"] / f["conversion_price"], 6)}


def main():
    test_cash, test_wc = segment_flow(10, 0.2, 2, 0.3, 0.05, 1)
    assert isclose(test_cash, 0.5) and test_wc == 3
    assert common_value(120, 9, 10, 10) == 12 and common_value(55, 9, 10, 10) == 5
    data = json.loads((HERE / "2026-Q3-input.json").read_text())
    details = {name: calculate(data, name) for name in data["paths"]}
    values = {key: row["per_share"] for key, row in details.items()}
    assert list(values.values()) == sorted(values.values())
    scenarios = {"currency":"CNY", **values, "horizon_note":"原业务按第五年扣研发税后经营利润估值，SHM按晶圆供应可见期逐年折现；乐观路径另给三年有条件延续。"}
    output = {"symbol":data["symbol"], "report_period":data["report_period"],
              "value_range":{"low":values["base_low"],"high":values["base_high"],"currency":"CNY"},
              "return_model":None, "scenarios":scenarios, "calculation":details}
    (HERE / "2026-Q3-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
