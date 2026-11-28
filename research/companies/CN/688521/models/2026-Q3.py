"""在本目录运行 python 2026-Q3.py，根据配套输入生成简明结果。"""
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def opening_positions(b):
    liquidity = b["cash_equivalents"] + b["trading_assets"] - b["repurchase_cash"] - b["operating_liquidity"]
    claims = sum(b[k] for k in ("short_debt", "current_maturities", "long_debt", "lease_liability",
                                 "deferred_asset_payment", "minority_put"))
    working = sum(b[k] for k in ("receivables", "contract_assets", "inventory", "advances_to_suppliers"))
    working -= b["payables"] + b["customer_advances"]
    shares = b["issued_shares"] - b["treasury_shares"] + b["award_budget"]
    return liquidity - claims, working, shares


def continuing_dcf(nopat, s):
    """第六至十年增速线性回落，第十一年起维持长期增长。"""
    total = 0
    long_growth = s["perpetual_growth"]
    for year in range(1, 6):
        growth = s["fade_growth"] + (long_growth - s["fade_growth"]) * (year - 1) / 4
        investment = nopat * growth / s["future_roic"]
        nopat *= 1 + growth
        total += (nopat - investment) / (1 + s["discount"]) ** year
    perpetual_cash = nopat * (1 + long_growth - long_growth / s["future_roic"])
    return total + perpetual_cash / (s["discount"] - long_growth) / (1 + s["discount"]) ** 5


def per_share(operating_value, financial_balance, shares, discount, years):
    terminal = max(0, (operating_value + financial_balance) / shares)
    return terminal, terminal / (1 + discount) ** years


def evaluate(s, opening, tax):
    funding, working, shares = opening
    initial_funding = funding
    flow_sum = 0
    first_working = None
    cumulative_capex = 0
    peak_need = max(0, -funding)
    for i, (revenue, margin) in enumerate(zip(s["revenue"], s["ebit_margin"]), start=1):
        operating_income = revenue * margin
        nopat = operating_income - max(0, operating_income) * tax
        next_working = revenue * s["working_capital_share"]
        net_capex = revenue * s["net_capex_share"]
        funding_charge = max(0, -funding) * s["funding_cost"]
        flow = nopat - (next_working - working) - net_capex - funding_charge
        funding += flow
        flow_sum += flow
        peak_need = max(peak_need, -funding)
        working = next_working
        if i == 1:
            first_working, first_nopat = working, nopat
        else:
            cumulative_capex += net_capex
    assert isclose(funding, initial_funding + flow_sum, abs_tol=1e-8)
    terminal, present = per_share(nopat * s["multiple"], funding, shares, s["discount"], 5)
    _, cross = per_share(continuing_dcf(nopat, s), funding, shares, s["discount"], 5)
    return {k: round(v, 2) for k, v in {
        "present": present, "year5": terminal, "dcf_check": cross, "year5_nopat": nopat,
        "year5_net_financial_position": funding, "peak_net_funding_need": peak_need,
        "y1_to_y5_increase_in_nopat": nopat - first_nopat,
        "y1_to_y5_net_investment": working - first_working + cumulative_capex
    }.items()}


def main():
    # 手算：经营价值90、金融净负债2，4亿股，第五年每股22；贴现率为零时现值亦为22。
    assert per_share(90, -2, 4, 0, 5) == (22, 22)
    # 平稳NOPAT 4、零增长且资金成本10%，第五年经营持续价值应为40。
    steady = {"fade_growth": 0, "perpetual_growth": 0, "future_roic": 0.16, "discount": 0.1}
    assert isclose(continuing_dcf(4, steady), 40)
    p = json.loads((ROOT / "2026-Q3-input.json").read_text())
    opening = opening_positions(p["opening"])
    details = {k: evaluate(s, opening, p["tax_on_positive_operating_profit"]) for k, s in p["scenarios"].items()}
    anchors = {k: v["present"] for k, v in details.items()}
    assert list(anchors.values()) == sorted(anchors.values())
    assert 5.38 < opening[2] < 5.40 and opening[1] < 0
    value_range = {"currency": "CNY", "low": anchors["base_low"], "high": anchors["base_high"]}
    terminal = {"low": details["base_low"]["year5"], "high": details["base_high"]["year5"]}
    return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY",
                    "model_as_of": p["model_as_of"], "base_case_distributions_per_share": [0] * 5,
                    "base_case_terminal_equity_value_range_per_share": {"year_5": terminal}}
    result = {"symbol": p["symbol"], "report_period": p["report_period"], "value_range": value_range,
              "return_model": return_model, "scenarios": dict(currency="CNY", horizon_note=p["horizon_note"], **anchors),
              "opening_net_financial_position": round(opening[0], 2), "opening_working_capital": round(opening[1], 2),
              "diluted_shares_100m": round(opening[2], 4), "economic_paths": details}
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
