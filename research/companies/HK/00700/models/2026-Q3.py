"""在本文件目录读取同名前缀的输入，生成可独立复算的普通股价值和回报。"""
import json
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent


def holder_value(dividends, terminal, rate):
    return sum(amount / (1 + rate) ** year
               for year, amount in enumerate(dividends, start=1)) + terminal / (1 + rate) ** len(dividends)


def opening_shares(facts):
    return (facts["issued_oct"] - facts["pending_cancel_oct"] + facts["options_new_oct"]
            + facts["awards_granted_not_settled_q3"] - facts["trust_proxy_h1"])


def opening_cash(facts, cfg):
    return (facts["net_cash"] - cfg["operating_cash_buffer"] - cfg["oct_net_cash_use_estimate"]
            - cfg["outside_holders_net_cash"])


def project(data, case, rate, growth):
    facts, cfg, path = data["facts"], data["shared"], data["paths"][case]
    fx = facts["rmb_per_hkd"]
    shares = opening_shares(facts)
    starting_shares = shares
    revenue = facts["revenue_9m"] + facts["revenue_prior_q4"]
    cash = opening_cash(facts, cfg)
    portfolio = facts["listed_investments"] * cfg["listed_realisation"] + facts["unlisted_investments"] * cfg["unlisted_realisation"]
    dividends, net_buybacks, rows = [], [], []
    for t, sales_growth in enumerate(path["growth"]):
        revenue *= 1 + sales_growth
        gross_cash = revenue * (path["cash_margin"][t] - cfg["content_and_lease_pct"])
        free_cash = (gross_cash - path["capex_cash"][t] - path["incremental_compute_advances"][t]) * cfg["parent_fraction"]
        interest = cash * (cfg["reserve_yield"] if cash >= 0 else path["borrowing_rate"])
        investment_payment = cfg["outstanding_investment_commitment"] if t == 0 else 0
        portfolio += investment_payment * cfg["unlisted_realisation"]
        budget = min(cfg["parent_cash_available"][t], max(0, free_cash + interest - investment_payment))
        award_shares = cfg["new_dilutive_shares_pa"]
        repurchase_price = cfg["gross_buyback_hkd_price"] * (1 + cfg["buyback_price_growth"]) ** t
        # 股息先预留，包括本年新授权益；随后注销，余下的股息拨备返还留存。
        declared = min(path["dividend_hkd"][t], budget / ((shares + award_shares) * fx))
        reserved = declared * (shares + award_shares) * fx
        repurchased_cash = min(path["gross_buyback_hkdbn"][t] * fx, max(0, budget - reserved))
        repurchased_shares = repurchased_cash / (repurchase_price * fx)
        next_shares = shares + award_shares - repurchased_shares
        paid_dividend = declared * next_shares * fx
        next_cash = cash + free_cash + interest - investment_payment - paid_dividend - repurchased_cash
        assert isclose(next_cash - cash + paid_dividend + repurchased_cash + investment_payment, free_cash + interest, abs_tol=1e-8)
        assert isclose(shares - next_shares, repurchased_shares - award_shares, abs_tol=1e-8)
        dividends.append(declared)
        net_buybacks.append((repurchased_shares - award_shares) * repurchase_price / starting_shares)
        rows.append({"revenue": round(revenue, 2), "owner_cash_before_awards": round(free_cash, 2),
                     "dividend_cash": round(paid_dividend, 2), "buyback_cash": round(repurchased_cash, 2),
                     "repurchased_m_shares": round(1000 * repurchased_shares, 2),
                     "closing_net_cash_after_buffer": round(next_cash, 2), "diluted_bn": round(next_shares, 5)})
        shares, cash = next_shares, next_cash

    # 年六起以现金等价物承担新授权益，完全稀释股数固定；保留年五的资本开支强度。
    capitalised_cash = free_cash - award_shares * repurchase_price * fx
    going_concern = capitalised_cash * (1 + growth) / (rate - growth)
    terminal = (going_concern + cash + portfolio) / (shares * fx)
    value = holder_value(dividends, terminal, rate)
    return {"value": round(value, 2), "terminal": round(terminal, 2),
            "terminal_pv_share": round(terminal / (1 + rate) ** 5 / value, 4),
            "net_buyback_per_share": round(sum(net_buybacks) / len(net_buybacks), 2),
            "dividends": [round(x, 6) for x in dividends], "portfolio": round(portfolio, 2), "years": rows}


def main():
    data = json.loads((HERE / "2026-Q3-input.json").read_text())
    assert isclose(holder_value([2, 2], 10, 0.1), 2 / 1.1 + 12 / 1.21)
    endpoints = {name: project(data, *terms) for name, terms in data["endpoints"].items()}
    anchors = {name: result["value"] for name, result in endpoints.items()}
    assert list(anchors.values()) == sorted(anchors.values()) and min(anchors.values()) > 0
    low, high = endpoints["base_low"], endpoints["base_high"]
    assert low["dividends"] == high["dividends"]
    facts, cfg = data["facts"], data["shared"]
    ebit_after_tax = facts["operating_profit_9m"] * 4 / 3 * (1 - cfg["peer_check_parent_tax_rate"]) * cfg["parent_fraction"]
    bridge = low["portfolio"] + opening_cash(facts, cfg) - cfg["outstanding_investment_commitment"]
    diluted = opening_shares(facts)
    check = [round((ebit_after_tax * multiple + bridge) / (diluted * facts["rmb_per_hkd"]), 2)
             for multiple in cfg["check_core_multiples"]]
    output = {"symbol": data["symbol"], "report_period": data["report_period"],
              "value_range": {"low": low["value"], "high": high["value"], "currency": "HKD"},
              "scenarios": {"currency": "HKD", **anchors, "horizon_note": data["horizon_note"]},
              "return_model": {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
                               "model_as_of": data["as_of"], "base_case_distributions_per_share": low["dividends"],
                               "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low["terminal"], "high": high["terminal"]}}},
              "annual_net_buyback_per_share": low["net_buyback_per_share"], "cross_check": check,
              "base_cash_bridge": low["years"], "terminal_pv_fraction": [low["terminal_pv_share"], high["terminal_pv_share"]]}
    (HERE / "2026-Q3-output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
