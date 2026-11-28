"""粤海投资普通股分配模型。python 2026-Q3.py 可在任意工作目录复算。"""
from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "2026-Q3-input.json").read_text())
F = DATA["facts"]
A = DATA["assumptions"]
SHARES = DATA["shares"]
TAX = A["tax_proxy"]

def pv(cashflows, rate):
    return sum(cash / (1 + rate) ** year for year, cash in enumerate(cashflows, 1))

def normalized_profits():
    profit = F["continuing_profit_2025"] + F["continuing_profit_9m26"] - F["continuing_profit_9m25"]
    profit -= F["disposal_gain_pretax"] * (1 - TAX)
    dongshen = (F["dongshen_pretax_2025"] + F["dongshen_pretax_9m26"] - F["dongshen_pretax_9m25"])
    dongshen *= math.prod(F["dongshen_indirect_holding"]) * (1 - TAX)
    road = F["road_pretax_9m26"] * 4 / 3 * (1 - TAX) * F["road_ownership"]
    other = profit - dongshen - road
    assert math.isclose(profit, dongshen + other + road) and other > 0
    return dongshen, other, road

def value(path):
    dongshen, other, road = normalized_profits()
    old_end = 3 + A["old_contract_fraction_year4"]
    new_end = old_end + path["renewal_years"]
    rate = path["required_return"]
    flows = []
    end = max(A["road_years"], math.ceil(new_end), 5)
    for year in range(1, end + 1):
        old = max(0, min(1, old_end - year + 1))
        renewed = max(0, min(year, new_end) - max(year - 1, old_end))
        assert 0 <= old + renewed <= 1.00000001
        # 原约利润缓慢上行，续期从届满前的经营水平起算，随后保持名义平稳。
        trough_weight = max(0, (4 - year) / 3) if path.get("cyclical") else 1
        dongshen_factor = 1 + (path["dongshen_factor"] - 1) * trough_weight
        other_factor = 1 + (path["other_profit_factor"] - 1) * trough_weight
        pre_profit = dongshen * dongshen_factor * (1 + path["dongshen_growth"]) ** min(year - 1, 3)
        water_profit = pre_profit * (old + renewed * path["renewed_net_profit_fraction"])
        other_profit = other * other_factor * (1 + path["other_growth"]) ** min(year - 1, 4)
        other_profit *= (1 + A["other_steady_growth"]) ** max(0, year - 5)
        road_profit = road if year <= A["road_years"] else 0
        total = water_profit + other_profit + road_profit
        payout = path["first_five_payout"] if year <= 5 else path["mature_payout"]
        if path.get("cyclical") and year <= 5:
            payout = 0.65 + (payout - 0.65) * trough_weight
        entry_cost = path["renewal_cost_bn"] if year == 4 else 0
        dividend = max(0, total * payout - entry_cost)
        retained = total - dividend - entry_cost
        assert retained >= 0 and math.isclose(total, dividend + retained + entry_cost)
        flows.append(dividend / SHARES)
    # 两项专营权到期后归零，尾值仅保留其他业务组合。
    growth = A["other_steady_growth"]
    tail = other_profit * (1 + growth) * path["mature_payout"] / (rate - growth) / SHARES
    terminal = pv(flows[5:], rate) + tail / (1 + rate) ** (end - 5)
    value_today = pv(flows[:5], rate) + terminal / (1 + rate) ** 5
    assert math.isclose(value_today, pv(flows, rate) + tail / (1 + rate) ** end)
    return {"value": round(value_today, 2), "distributions": [round(x, 4) for x in flows[:5]],
            "terminal": round(terminal, 2), "terminal_pv_share": round(terminal / (1 + rate) ** 5 / value_today, 3)}

def main():
    # 零增长年付1港元，10%折现、第五年附10港元终值，现值恰为10港元。
    assert math.isclose(pv([1, 1, 1, 1, 11], 0.1), 10)
    paths = {k: dict(zip(DATA["scenario_columns"], row, strict=True)) for k, row in DATA["scenarios"].items()}
    paths["cyclical_bear"]["cyclical"] = True
    results = {k: value(s) for k, s in paths.items()}
    values = [r["value"] for r in results.values()]
    assert values == sorted(values)
    low, high = results["base_low"], results["base_high"]
    assert low["distributions"] == high["distributions"]
    amounts = normalized_profits()
    multiples = A["secondary_earnings_multiples"]
    check = [round(sum(amount * multiples[name][i] for amount, name in zip(amounts, ["dongshen","other","road"])) / SHARES, 2) for i in range(2)]
    no_renew = dict(paths["base_low"], renewed_net_profit_fraction=0, renewal_years=0, renewal_cost_bn=0)
    model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "HKD",
             "model_as_of": DATA["as_of"], "base_case_distributions_per_share": low["distributions"],
             "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": low["terminal"], "high": high["terminal"]}}}
    result = {"symbol": "HK:00270", "report_period": "2026-Q3",
              "value_range": {"low": low["value"], "high": high["value"], "currency": "HKD"},
              "return_model": model, "scenarios": results, "secondary_range": check,
              "no_renewal_other_inputs_constant": value(no_renew)["value"],
              "normalised_earnings_bn": dict(zip(["dongshen", "other", "road"], map(lambda x: round(x, 3), amounts)))}
    (ROOT / "2026-Q3-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")

if __name__ == "__main__":
    main()
