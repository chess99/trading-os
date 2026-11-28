"""海尔智家 H 股。复用同季发行人现金账，重算每一情景。运行本文件，简明结果输出至 stdout。"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "2026-Q3-input.json").read_text())
ISSUER = next(p / DATA["issuer_models"] for p in HERE.parents if (p / DATA["issuer_models"]).is_dir())
sys.dont_write_bytecode = True
sys.path.insert(0, str(ISSUER / "2026-Q3"))
import baseline
import cash_replay
from bridge_core import Context

BN = 1_000_000_000


def equity_bridge(data, original):
    event = original["financial_inputs"]["event"]
    a_buys = data["a_repurchases_nov"]
    a_new = sum(row[2] for row in a_buys)
    a_inventory = data["a_treasury_nov27"]
    assert a_inventory == data["a_treasury_oct31"] + sum(row[1] for row in a_buys)
    a_remaining = float(event["new_future"]) - a_new
    cumulative_paid = data["a_nov20_cumulative_cost_cny"] + a_buys[-1][2]
    assert math.isclose(cumulative_paid + a_remaining, float(event["plan_minimum"]), abs_tol=.01)
    h_buys = data["h_pending_repurchases"]
    h_count = sum(row[1] for row in h_buys)
    h_paid_hkd = sum(row[2] for row in h_buys)
    d_euros = data["d_tender_shares"] * data["d_tender_eur_per_share"]
    d_paid = d_euros * data["d_cny_per_eur_estimate"]
    h_paid = h_paid_hkd * data["cny_per_hkd"]
    diluted = sum(data["issued"].values()) - h_count - data["d_prior_pending"] - data["d_tender_shares"]
    return dict(eligible_now=diluted-a_inventory, diluted_after_employee_delivery=diluted,
                a_inventory=a_inventory, a_remaining_cny=round(a_remaining, 2),
                a_nov_paid_cny=round(a_new, 2), h_pending_shares=h_count, h_paid_hkd=h_paid_hkd,
                h_paid_cny_estimate=h_paid, d_tender_cny_estimate=d_paid,
                d_embedded_y1_cny=float(event["independent_D_tender"]))


def present_value(distributions, rate):
    return math.fsum(cash / (1+rate)**year for year, cash in enumerate(distributions, 1))


def eligible_at_year_end(bridge, year):
    unvested = bridge["a_inventory"] * max(0, 3-year)/3
    return bridge["diluted_after_employee_delivery"] - unvested


class CurrentCapital(Context):
    """原现金账预设首年支付 D 股款。本期将该项移至期初，并保留 A 股计划余款。"""

    def debit(self, cash, state):
        after_original_a = super().debit(cash, state)
        extra = self.bridge["a_nov_paid_cny"] + self.bridge["h_paid_cny_estimate"] + self.bridge["d_tender_cny_estimate"]
        cash_left = after_original_a - extra/BN
        assert cash_left > 0
        return cash_left

    def future(self, original):
        # 原引擎的买回总支出为固定 D 要约预算 + 本返回值；抵回已移到期初的 D 款。
        return (self.bridge["a_remaining_cny"] - self.bridge["d_embedded_y1_cny"]) / BN


def run_path(branch, shock, entry, rate, original, bridge):
    years = original["financial_inputs"]["cases"][0]["years"]
    issuer = baseline.calculate(rate, shock, entry, years)
    assert issuer["status"] == "feasible"
    cash_replay.CTX = CurrentCapital("600690", branch, issuer, original["financial_inputs"]["event"], True)
    cash_replay.CTX.bridge = bridge
    ledger = cash_replay.calculate(rate, shock, entry, years)
    assert ledger["status"] == "feasible"
    states = ledger["states"]
    assert math.isclose(states[0]["buyback_cash"] * BN, bridge["a_remaining_cny"], abs_tol=.01)
    fx = DATA["cny_per_hkd"]
    cash = []
    for row in states:
        shares = eligible_at_year_end(bridge, row["year"])
        distribution = row["common_dividend"] * BN / shares / fx
        assert math.isclose(distribution * shares * fx, row["common_dividend"] * BN, abs_tol=.01)
        cash.append(distribution)
    tail = cash[-1] * 1.015 / (rate-.015) / (1+rate)**years
    assert tail < 1e-8
    current = present_value(cash, rate) + tail
    year5 = present_value(cash[5:], rate) + tail * (1+rate)**5
    assert math.isclose(present_value(cash[:5], rate) + year5/(1+rate)**5, current)
    return dict(current=current, distributions=cash[:5], year5=year5,
                terminal_share=year5/(1+rate)**5/current)


def main():
    assert __debug__
    assert math.isclose(present_value([11, 12.1], .10), 20)
    assert eligible_at_year_end(dict(a_inventory=30, diluted_after_employee_delivery=100), 1) == 80
    original = json.loads((ISSUER / "2026-Q3-input.json").read_text())
    bridge = equity_bridge(DATA, original)
    cases = {key: run_path(key, shock, entry, rate, original, bridge) for key, shock, entry, rate in DATA["cases"]}
    anchors = {key: round(cases[key]["current"], 2) for key in ("structural_bear","cyclical_bear","base_low","base_high","bull")}
    assert list(anchors.values()) == sorted(anchors.values())
    out = dict(symbol=DATA["symbol"], report_period=DATA["report_period"],
               value_range=dict(currency="HKD",low=anchors["base_low"],high=anchors["base_high"]),
               return_model=dict(schema_version=1,method="annual_common_equity_irr_v1",currency="HKD",
                   model_as_of=DATA["information_cutoff"],
                   base_case_distributions_per_share=[round(x, 6) for x in cases["central"]["distributions"]],
                   base_case_terminal_equity_value_range_per_share={"year_5":{
                       "low": round(cases["base_low"]["year5"], 6), "high": round(cases["base_high"]["year5"], 6)}}),
               scenarios={"currency":"HKD", **anchors}, equity_bridge=bridge,
               central_value_hkd=cases["central"]["current"], product_value_hkd=cases["product"]["current"],
               terminal_share=cases["central"]["terminal_share"])
    print(json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
